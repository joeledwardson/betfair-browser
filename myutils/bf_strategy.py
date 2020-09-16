from flumine import FlumineBacktest, clients, BaseStrategy
from flumine.order.order import BaseOrder, BetfairOrder, OrderStatus
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue
from betfairlightweight import APIClient

import json
from myutils import betting
import os
import pandas as pd
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

OC_EXCHANGES = ['BF', 'MK', 'MA', 'BD', 'BQ']
active_logger = logging.getLogger(__name__)

# increment 'window_index' until its timestamp is within 'seconds_window' seconds of the current record timestamp, returns
# updated 'window_index' value.
# if 'outside_window' is specified as True, 'window_index' will be incremented until it preceeds the record within
# the specified window - if False, 'window_index' will be incvremented until it is the first record within the specified
# window
def update_index_window(
        records: List,
        current_index, # index of current record - if streaming this will just be the last record, needed for historical list
        seconds_window, # size of the window in seconds
        window_index, # index of window start to be updated and returned
        outside_window=True,
        f_pt=lambda r, i: r[i][0].publish_time):

    t = f_pt(records, current_index)
    while (window_index + outside_window) < current_index and \
            (t - f_pt(records, window_index + outside_window)).total_seconds() > seconds_window:
        window_index += 1
    return window_index


class WindowProcessorBase:

    @classmethod
    def processor_init(cls, window: dict):
        pass

    @classmethod
    def update_window(self, market_list: List[MarketBook], new_book: MarketBook, window: dict):
        raise NotImplementedError

class WindowProcessorTradedVolume(WindowProcessorBase):

    @classmethod
    def processor_init(cls, window: dict):
        window['old_tv_ladders'] = {}

    @classmethod
    def update_window(cls, market_list: List[MarketBook], new_book: MarketBook, window: dict):

        if window['window_index'] != window['window_prev_index']:

            window['old_tv_ladders'] = {
                runner.selection_id: runner.ex.traded_volume
                for runner in market_list[window['window_prev_index']].runners}

        window['tv_diffs'] = {
            runner.selection_id: betting.get_record_tv_diff(
                runner.ex.traded_volume,
                window['old_tv_ladders'].get(runner.selection_id) or {},
                is_dict=True)
            for runner in new_book.runners
        }

class Windows:

    @staticmethod
    def func_publish_time(record, index):
        return record[index].publish_time

    functions = {
        'WindowProcessorTradedVolume': WindowProcessorTradedVolume
    }

    def __init__(self):
        self.windows = {}

    def add_window(self, width_seconds) -> Dict:
        if width_seconds not in self.windows:
            self.windows[width_seconds] = {
                'window_prev_index': 0,
                'window_index': 0,
                'functions': []
            }
        return self.windows[width_seconds]

    def add_function(self, width_seconds, function_key):
        window = self.windows[width_seconds]
        if function_key not in window['functions']:
            window['functions'].append(function_key)
            self.functions[function_key].processor_init(window)

    def update_windows(self, market_list: List[MarketBook], new_book: MarketBook):
        for width_seconds, w in self.windows.items():
            w['window_prev_index'] = w['window_index']
            w['window_index'] = update_index_window(
                records=market_list,
                current_index=len(market_list) - 1,
                seconds_window=width_seconds,
                window_index=w['window_index'],
                outside_window=True,
                f_pt=self.func_publish_time)
            w['id_index'] = {
                runner.selection_id: i for i, runner in enumerate(new_book.runners)
            }
            for f in w['functions']:
                self.functions[f].update_window(market_list, new_book, w)

class RunnerFeatureBase:

    def __init__(self, selection_id):
        self.selection_id = selection_id
        self.values = []
        self.dts = []

    def get_data(self):
        return {'x': self.dts, 'y': self.values}

    def process_runner(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        value = self.runner_update(market_list, new_book, windows, runner_index)
        if value:
            self.dts.append(new_book.publish_time)
            self.values.append(value)

    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        raise NotImplementedError


class RunnerFeatureTradedWindowBase(RunnerFeatureBase):
    def __init__(self, selection_id, window_s, windows: Windows):
        super().__init__(selection_id)
        self.window = windows.add_window(window_s)
        windows.add_function(window_s, 'WindowProcessorTradedVolume')

class RunnerFeatureTradedWindowMin(RunnerFeatureTradedWindowBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        prices = [tv['price'] for tv in self.window['tv_diffs'][self.selection_id]]
        return min(prices) if prices else None

class RunnerFeatureTradedWindowMax(RunnerFeatureTradedWindowBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        prices = [tv['price'] for tv in self.window['tv_diffs'][self.selection_id]]
        return max(prices) if prices else None

class RunnerFeatureLTP(RunnerFeatureBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        return new_book.runners[runner_index].last_price_traded

class CandleStick:
    def __init__(self, time_frame_seconds):
        self.raw_values = []
        self.raw_datetimes = []
        self.window_index = 0
        self.candlesticks = {
            'open': [],
            'close': [],
            'high': [],
            'low': [],
            'x': [],
        }
        self.last_timestamp = None
        self.width_s = time_frame_seconds
        self.previous_close = None

    def new_value(self, timestamp, value):
        self.raw_values.append(value)
        self.raw_datetimes.append(timestamp)
        self.last_timestamp = self.last_timestamp or timestamp

        n_values = len(self.raw_values)

        while 1:

            # start and end of current candlestick window
            candle_start_dt = self.last_timestamp
            candle_end_dt = self.last_timestamp + timedelta(seconds=self.width_s)

            # current timestamp must have completed current candlestick window, and must have at least 1 value
            if timestamp < candle_end_dt or n_values == 0:
                break

            # set starting index of candlestick values
            candle_index = self.window_index

            # increment whilst value timestamps are within candlestick window
            while candle_index < n_values and self.raw_datetimes[candle_index] < candle_end_dt:
                candle_index += 1

            # slice values of candlestick start to end
            candle_vals = self.raw_values[self.window_index:candle_index]

            # if no values exist, use previous value
            # (impossible on first entry as cannot reach here without at least 1 value and 1st value being beyond candlestick end)
            if not candle_vals:
                candle_vals = [self.previous_close]

            # add to candlestick list
            for k, v in {
                'x': self.last_timestamp,
                'open': candle_vals[0],
                'close': candle_vals[-1],
                'high': max(candle_vals),
                'low': min(candle_vals)
            }.items():
                self.candlesticks[k].append(v)

            # update starting index for candlestick to the next index from the end of current candlestick
            self.window_index = candle_index

            # update new candlestick starting timestamp to end of candlestick just written
            self.last_timestamp = candle_end_dt

            # store 'close' value of candlestick
            self.previous_close = candle_vals[-1]


class RunnerFeatureCandleStickBase(RunnerFeatureBase):
    def __init__(self, selection_id, candlestick_s):
        super().__init__(selection_id)
        self.candlestick = CandleStick(candlestick_s)

    def process_runner(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        value = self.runner_update(market_list, new_book, windows, runner_index)
        if value:
            self.candlestick.new_value(new_book.publish_time, value)

    def get_data(self):
        return self.candlestick.candlesticks

class RunnerFeatureWOM(RunnerFeatureCandleStickBase):

    def __init__(self, selection_id, candlestick_s=1, wom_ticks=3):
        super().__init__(selection_id, candlestick_s)
        self.wom_ticks = wom_ticks

    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        atl = new_book.runners[runner_index].ex.available_to_lay
        atb = new_book.runners[runner_index].ex.available_to_back

        if atl and atb:
            back = sum([x['size'] for x in atb[:self.wom_ticks]])
            lay = sum([x['size'] for x in atl[:self.wom_ticks]])
            return back - lay
        else:
            return None


# sort oddschecker dataframe by avergae value
def sort_oc(df: pd.DataFrame):
    # get means across columns
    avgs = df.mean(axis=1)
    return avgs.sort_values()


# get historical oddschecker file
def get_hist_oc_df(oc_path):
    try:
        return pd.read_pickle(oc_path)
    except Exception as e:
        active_logger.warning(f'error getting oc file: "{e}"', exc_info=True)
        return None


# create oddschecker historic path
def get_hist_oc_path(dir_path, market_id, oc_subdir='oddschecker'):
    return os.path.join(dir_path, oc_subdir, market_id)


# strip exchanges from oddschecker odds dataframe columns and dataframe index (names) with selection IDs
# on fail, will log an error and return None
def process_oc_df(df: pd.DataFrame, name_id_map):

    df = df[[col for col in df.columns if col not in OC_EXCHANGES]]
    oc_ids = betting.names_to_id(df.index, name_id_map)
    if not oc_ids:
        return None

    df.index = oc_ids
    return df


# filter orders to runner
def filter_orders(orders, selection_id) -> List[BaseOrder]:
    return [o for o in orders if o.selection_id == selection_id]


# get betfair catalogue file
def get_hist_cat(catalogue_path) -> MarketCatalogue:
    try:
        with open(catalogue_path) as f:
            dat = f.read()
        cat = json.loads(dat)
        return MarketCatalogue(**cat)
    except Exception as e:
        active_logger.warning(f'error getting catalogue "{e}"', exc_info=True)
        return None


# generate betfair catalogue file path
def get_hist_cat_path(dir_path, market_id, bf_cat_subdir='bf_catalogue'):
    return os.path.join(dir_path, bf_cat_subdir, market_id)


# generate betfair streaming file path
def get_hist_stream_path(dir_path, market_id, bf_stream_subdir='bf_stream'):
    return os.path.join(dir_path, bf_stream_subdir, market_id)


# get historical betfair stream data
def get_hist_stream_data(trading: APIClient, stream_path: str) -> List[List[MarketBook]]:

    stream_logger = logging.getLogger('betfairlightweight.streaming.stream')
    level = stream_logger.level

    if not os.path.isfile(stream_path):

        logging.warning(f'stream path "{stream_path}" does not exist')
        return None

    else:

        try:

            # stop it winging about stream latency
            stream_logger.setLevel(logging.CRITICAL)
            q = betting.get_historical(trading, stream_path)
            # reset level
            stream_logger.setLevel(level)
            return list(q.queue)

        except Exception as e:

            stream_logger.setLevel(level)
            logging.warning(f'error getting historical: "{e}"', exc_info=True)
            return None


# lay if below bookmaker price
def lay_low(
        strategy: BaseStrategy,
        runner: RunnerBook,
        market: Market,
        bookie_odds: float,
        stake_size):

    # d = market.mydat
    # TODO - implement check for runner in oddschecker dataframe
    # if runner.selection_id not in list(d['oc_df'].index)
    # orders = market.blotter._orders.values()

    # check if runner ID not found in oddschecker list, or already has an order
    if  not(filter_orders(market.blotter, runner.selection_id)):
        return

    atl = runner.ex.available_to_lay
    if not atl:
        return

    price = atl[0]['price']
    size = atl[0]['size']

    if not float(price) < float(bookie_odds):
        return

    if price < 1:
        return

    active_logger.info(f'runner id "{runner.selection_id}" best atl {price} for £{size}, bookie avg is {bookie_odds}')

    trade = Trade(
        market_id=market.market_id,
        selection_id=runner.selection_id,
        handicap=runner.handicap,
        strategy=strategy)
    lay_order = trade.create_order(
        side='LAY',
        order_type=LimitOrder(
            price=price,
            size=stake_size
        ))
    strategy.place_order(market, lay_order)


# back if above back_scale*bookie_odds
def back_high(
        strategy: BaseStrategy,
        runner: RunnerBook,
        market: Market,
        back_scale,
        bookie_odds: float,
        stake_size):

    # orders = market.blotter._orders.values()

    # check if runner ID not found in oddschecker list, or already has an order
    if  not(filter_orders(market.blotter, runner.selection_id)):
        return

    atb = runner.ex.available_to_back
    if not atb:
        return

    price = atb[0]['price']
    size = atb[0]['size']

    if price < 1:
        return

    if not float(price) > back_scale * float(bookie_odds):
        return

    active_logger.info(f'runner id "{runner.selection_id}" best atb {price} for £{size}, bookie max is {bookie_odds}')

    trade = Trade(
        market_id=market.market_id,
        selection_id=runner.selection_id,
        handicap=runner.handicap,
        strategy=strategy)
    back_order = trade.create_order(
        side='BACK',
        order_type=LimitOrder(
            price=price,
            size=stake_size
        ))
    strategy.place_order(market, back_order)


# cancel an order if unmatched after 'wait_complete_seconds'
def cancel_unmatched(
        order: BaseOrder,
        wait_complete_seconds=2.0):
    if order.status != OrderStatus.EXECUTION_COMPLETE:
        if order.elapsed_seconds >= wait_complete_seconds:
            active_logger.info('cancelling order on "{0}", {1} £{2:.2f} at {3}'.format(
                order.selection_id,
                order.side,
                order.order_type.size,
                order.order_type.price
            ))
            order.cancel()


# green a runner - runner's active orders will be left to complete for 'wait_complete_seconds', and minimum exposure
# to require greening is 'min_green_pence'
def green_runner(
        strategy: BaseStrategy,
        runner: RunnerBook,
        market: Market,
        wait_complete_seconds=2.0,
        min_green_pence=10):

    orders = filter_orders(market.blotter, runner.selection_id)

    if not orders:
        return

    # check all orders for runner have been given at least minimum time to process
    if not all([o for o in orders if o.elapsed_seconds >= wait_complete_seconds]):
        active_logger.debug(f'waiting for orders on "{runner.selection_id}" to exceed {wait_complete_seconds} seconds')
        return

    active_logger.debug(f'attempting to green "{runner.selection_id}"')

    back_profit = sum([
        (o.average_price_matched - 1 or 0)*(o.size_matched or 0) for o in orders
        if o.status==OrderStatus.EXECUTABLE or o.status==OrderStatus.EXECUTION_COMPLETE
           and o.side=='BACK'])
    lay_exposure = sum([
        (o.average_price_matched - 1 or 0)*(o.size_matched or 0) for o in orders
        if o.status==OrderStatus.EXECUTABLE or o.status==OrderStatus.EXECUTION_COMPLETE
           and o.side=='LAY'])

    outstanding_profit = back_profit - lay_exposure
    active_logger.debug(f'runner has £{back_profit:.2f} back profit and £{lay_exposure:.2f}')

    if not abs(outstanding_profit) > min_green_pence:
        return

    if outstanding_profit > 0:
        side = 'LAY'
        available = runner.ex.available_to_lay
        if not available:
            active_logger.debug('no lay options to green')
            return
    else:
        side = 'BACK'
        available = runner.ex.available_to_back
        if not available:
            active_logger.debug('no back options to green')
            return

    green_price = available[0]['price']
    green_size = round(abs(outstanding_profit) / (green_price - 1), 2)

    active_logger.info('greening active order on "{}", £{} at {}'.format(
        runner.selection_id,
        green_size,
        green_price,
    ))
    trade = Trade(
        market_id=market.market_id,
        selection_id=runner.selection_id,
        handicap=runner.handicap,
        strategy=strategy)
    green_order = trade.create_order(
        side=side,
        order_type=LimitOrder(
            price=green_price,
            size=green_size
        ))
    strategy.place_order(market, green_order)


# process market book in historical testing, result stored in 'mydat' dict attribute, applied to market object
# function searches for betfair catalogue file and oddschecker dataframe file
# - if processed successfuly, mydat['ok'] is True
def oc_hist_mktbk_processor(
        strategy: BaseStrategy,
        market: Market,
        market_book: MarketBook,
        dir_path,
        name_attr='name'):

    d = {
        'ok': False,
    }

    active_logger.info('processing new market "{}" {} {}'.format(
        market_book.market_id,
        market_book.market_definition.market_time,
        market_book.market_definition.event_name
    ))

    # get oddschecker dataframe from file
    oc_df = get_hist_oc_df(
        get_hist_oc_path(dir_path, market.market_id))
    if oc_df is None:
        return d

    # get betfair category from file
    cat = get_hist_cat(
        get_hist_cat_path(dir_path, market.market_id))
    if cat is None:
        return d

    # process oddschecker dataframe to set with selection IDs
    name_id_map = betting.get_names(cat, name_attr=name_attr, name_key=True)
    oc_df = process_oc_df(oc_df, name_id_map)
    if oc_df is None:
        return d

    # assign results to dict and write as market attribute
    oc_sorted = sort_oc(oc_df)
    d['oc_df'] = oc_df
    d['oc_sorted'] = oc_sorted
    d['id_fav'] = oc_sorted.index[0]
    d['id_outsider'] = oc_sorted.index[-1]
    d['cat'] = cat
    d['ok'] = True
    return d


class MyBaseStrategy(BaseStrategy):

    def check_market_book(self, market, market_book):
        # process_market_book only executed if this returns True
        if market_book.status != "CLOSED":
            return True

    # override default place order, this time printing where order validation failed
    # TODO - print reason for validation fail
    def place_order(self, market, order) -> None:
        runner_context = self.get_runner_context(*order.lookup)
        if self.validate_order(runner_context, order):
            runner_context.place()
            market.place_order(order)
        else:
            active_logger.warning(f'order validation failed for "{order.selection_id}"')


class BackTestClientNoMin(clients.BacktestClient):
    @property
    def min_bet_size(self) -> Optional[float]:
        return 0
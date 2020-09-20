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
import numpy as np
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import statistics
import statsmodels.api as sm
import operator

OC_EXCHANGES = ['BF', 'MK', 'MA', 'BD', 'BQ']
active_logger = logging.getLogger(__name__)

STREAM_SUBDIR = 'bf_stream'
CATALOGUE_SUBDIR = 'bf_catalogue'

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
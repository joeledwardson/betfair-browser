"""
Trade based on back/lay/ltp trend using regression
"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
import logging

from myutils.myclass import store_kwargs
from ...strategy.trademachine import tradestates as basestates
from mytrading.strategy.trademachine.trademachine import RunnerStateMachine
from ...strategy.featurestrategy import MyFeatureStrategy, MarketHandler
from ...process.ticks.ticks import LTICKS_DECODED, tick_spread, closest_tick
from ...process.prices import best_price, get_ltps
from mytrading.strategy.feature import RunnerFeatureBase
from .featuresconfig import get_trend_feature_configs
from . import states as trendstates
from .datatypes import TrendData, TrendCriteria


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyTrendStrategy(MyFeatureStrategy):
    """
    Take breach of LTP min/max windows as drift in specific direction and back/lay in the direction of drift
    """

    @store_kwargs(key_args='strategy_args', key_kwargs='strategy_kwargs')
    def __init__(
            self,
            criteria_kwargs: Dict,
            take_available: bool,
            tick_window: int,
            price_cutoff: float,
            stake_size: float,
            trade_transactions_cutoff: int,
            hold_ms: int,
            min_hedge_price: float,
            feature_kwargs: Dict,
            *args,
            **kwargs):

        super().__init__(*args, **kwargs)

        self.criteria_kwargs = criteria_kwargs
        self.trend_criteria = TrendCriteria(**criteria_kwargs)

        self.take_available = take_available
        self.tick_window = tick_window
        self.price_cutoff = price_cutoff
        self.stake_size = stake_size
        self.trade_transactions_cutoff = trade_transactions_cutoff
        self.hold_ms = hold_ms
        self.min_hedge_price = min_hedge_price
        self.feature_kwargs = feature_kwargs
        self.features_config = get_trend_feature_configs(**feature_kwargs)

        # market -> runner ID -> trend data
        self.trend_data_dicts: Dict[str, Dict[int, TrendData]] = dict()

    def create_state_machine(
            self,
            runner: RunnerBook,
            market: Market,
            market_book: MarketBook
    ) -> RunnerStateMachine:
        return RunnerStateMachine(
            states={
                state.name: state
                for state in [
                    basestates.TradeStateCreateTrade(),
                    trendstates.TrendTradeStateIdle(
                        criteria=self.trend_criteria,
                        trade_transactions_cutoff=self.trade_transactions_cutoff,
                        next_state=trendstates.TrendStateTypes.TREND_MONITOR_OPEN,
                    ),
                    trendstates.TrendTradeStateMonitorOpen(
                        stake_size=self.stake_size,
                        take_available=self.take_available,
                        name=trendstates.TrendStateTypes.TREND_MONITOR_OPEN,
                        next_state=[
                            basestates.TradeStateTypes.BIN,
                            trendstates.TrendStateTypes.TREND_HEDGE_PLACE,
                        ],
                    ),
                    trendstates.TrendTradeStateHedgePlace(
                        take_available=self.take_available,
                        min_hedge_price=self.min_hedge_price,
                        name=trendstates.TrendStateTypes.TREND_HEDGE_PLACE,
                        next_state=trendstates.TrendStateTypes.TREND_HEDGE_WAIT,
                    ),
                    trendstates.TrendTradeStateHedgeWait(
                        take_available=self.take_available,
                        name=trendstates.TrendStateTypes.TREND_HEDGE_WAIT,
                        next_state=basestates.TradeStateTypes.CLEANING,
                        hedge_place_state=trendstates.TrendStateTypes.TREND_HEDGE_PLACE,
                    ),
                    basestates.TradeStateBin(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStatePending(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price
                    ),
                    basestates.TradeStateHedgeWaitTake(
                        hedge_place_state=basestates.TradeStateTypes.HEDGE_TAKE_PLACE,
                    ),
                    basestates.TradeStateClean()
                ]
            },
            initial_state=basestates.TradeStateCreateTrade.name,
            selection_id=runner.selection_id,
        )

    def get_features_config(self, market, market_book, runner_index) -> Dict:
        return self.features_config

    def custom_market_initialisation(self, market: Market, market_book: MarketBook):
        self.trend_data_dicts[market.market_id] = dict()

    def custom_runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
        best_back = best_price(runner.ex.available_to_back)
        best_lay = best_price(runner.ex.available_to_lay)
        do_features = runner.last_price_traded and runner.last_price_traded <= self.price_cutoff and \
                      best_lay and best_lay <= self.price_cutoff and \
                      best_back and best_back <= self.price_cutoff
        self.trend_data_dicts[market_book.market_id][runner.selection_id] = TrendData(
            do_features=do_features
        )

    @staticmethod
    def tick_comp(feature: RunnerFeatureBase):
        return feature.sub_features['ticks'].sub_features['comparison'].last_value()

    def process_runner_features(self, mb: MarketBook, mh: MarketHandler, selection_id, runner_index):
        # only process features if allowed
        if self.trend_data_dicts[mb.market_id][selection_id].do_features:
            super().process_runner_features(mb, mh, selection_id, runner_index)

    def process_closed_market(self, market: Market, market_book: MarketBook) -> None:
        # only write feature file and order result if features are allowed
        if market.market_id in self.market_handlers:
            mh = self.market_handlers[market.market_id]
            if not mh.closed:
                for selection_id in list(mh.runner_handlers.keys()):
                    if not self.trend_data_dicts[market.market_id][selection_id].do_features:
                        del mh.runner_handlers[selection_id]
        super().process_closed_market(market, market_book)

    def trade_machine_kwargs(
            self,
            market: Market,
            market_book: MarketBook,
            runner_index: int,
    ) -> dict:

        runner = market_book.runners[runner_index]

        # get runner ID, trend data object and features dict
        selection_id = runner.selection_id
        trend_data = self.trend_data_dicts[market_book.market_id][selection_id]
        features = self.market_handlers[market_book.market_id].runner_handlers[selection_id].features

        # get smoothed features
        smoothed_back = features['best back smoothed']
        smoothed_lay = features['best lay smoothed']
        smoothed_ltp = features['ltp smoothed']

        # get trend data attributes
        lay_regression = smoothed_lay.sub_features['regression'].last_value() or {}
        back_regression = smoothed_back.sub_features['regression'].last_value() or {}
        ltp_regression = smoothed_ltp.sub_features['regression'].last_value() or {}

        # set gradient variables
        trend_data.lay_gradient = lay_regression.get('gradient')
        trend_data.lay_strength = lay_regression.get('rsquared')
        trend_data.back_gradient = back_regression.get('gradient')
        trend_data.back_strength = back_regression.get('rsquared')
        trend_data.ltp_gradient = ltp_regression.get('gradient')
        trend_data.ltp_strength = ltp_regression.get('rsquared')

        # set best back/best lay/ltp
        trend_data.best_back = best_price(runner.ex.available_to_back)
        trend_data.best_lay = best_price(runner.ex.available_to_lay)
        trend_data.ltp = runner.last_price_traded

        # set smoothed data values
        trend_data.smoothed_back = smoothed_back.last_value()
        trend_data.smoothed_lay = smoothed_lay.last_value()
        trend_data.smoothed_ltp = smoothed_ltp.last_value()

        # set spread
        trend_data.ladder_spread_ticks = features['spread'].last_value()

        # set LTP window spread
        ltp_max = features['ltp max'].last_value()
        ltp_min = features['ltp min'].last_value()
        if ltp_min is not None and ltp_max is not None:
            trend_data.window_spread_ticks = tick_spread(
                ltp_max,
                ltp_min,
                check_values=False
            )
        else:
            trend_data.window_spread_ticks = None

        # set tick movement values
        trend_data.back_tick_movement = self.tick_comp(smoothed_back)
        trend_data.lay_tick_movement = self.tick_comp(smoothed_lay)
        trend_data.ltp_tick_movement = self.tick_comp(smoothed_ltp)

        # set max tick movement values
        trend_data.back_max_diff_ticks = features['bckdif'].last_value()
        trend_data.lay_max_diff_ticks = features['laydif'].last_value()
        trend_data.ltp_max_diff_ticks = features['ltpdif'].last_value()

        # get ID for shortest runner from LTPs

        # list of runner ltps
        runner_ltps = get_ltps(market_book)

        # ltp tick indexes for runner ltps
        ltp_ticks = {k: closest_tick(v, return_index=True) for k, v in runner_ltps.items()}
        # shortest tick index of runner ltps
        shortest_ltp_tick = next(iter(ltp_ticks.values()), 0)
        # ltp tick index of selected runner
        ltp_tick = ltp_ticks.get(runner.selection_id, len(LTICKS_DECODED) - 1)

        return {
            'ltp_valid': abs(shortest_ltp_tick - ltp_tick) <= self.tick_window,
            'trend_data': trend_data,
        }

"""
Trade based on back/lay/ltp trend using regression
"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
import logging

from myutils.myclass import store_kwargs
from myutils.timing import timing_register
from ...trademachine import tradestates as basestates
from ...trademachine.trademachine import RunnerStateMachine
from ...strategy.featurestrategy import MyFeatureStrategy
from ...process.ticks.ticks import LTICKS_DECODED, tick_spread
from ...process.tradedvolume import traded_runner_vol
from ...process.prices import best_price, get_ltps
from ...feature.featureholder import FeatureHolder
from ...feature.features import RunnerFeatureBase
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
                        name=trendstates.TrendStateTypes.TREND_MONITOR_OPEN,
                        next_state=[
                            basestates.TradeStateTypes.BIN,
                            trendstates.TrendStateTypes.TREND_HEDGE_PLACE,
                        ],
                    ),
                    trendstates.TrendTradeStateHedgePlace(
                        min_hedge_price=self.min_hedge_price,
                        name=trendstates.TrendStateTypes.TREND_HEDGE_PLACE,
                        next_state=trendstates.TrendStateTypes.TREND_HEDGE_WAIT,
                    ),
                    trendstates.TrendTradeStateHedgeWait(
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
        self.trend_data_dicts[market_book.market_id][runner.selection_id] = TrendData()

    @staticmethod
    def tick_comp(feature: RunnerFeatureBase):
        return feature.sub_features['ticks'].sub_features['comparison'].last_value()

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
        trend_data.back_max_diff_ticks = features['best back max diff'].last_value()
        trend_data.lay_max_diff_ticks = features['best lay max diff'].last_value()
        trend_data.ltp_max_diff_ticks = features['ltp max diff'].last_value()

        # get ID for shortest runner from LTPs
        ltps = get_ltps(market_book)
        first_id = next(iter(ltps.keys()), 0)

        return {
            'first_runner': first_id == selection_id,
            'trend_data': trend_data,
        }

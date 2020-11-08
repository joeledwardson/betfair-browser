"""
Trade based on back/lay/ltp trend using regression
"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
import logging

from myutils.timing import timing_register
from ...trademachine import tradestates as basestates
from ...trademachine.trademachine import RunnerStateMachine
from ...strategy.featurestrategy import MyFeatureStrategy
from ...process.ticks.ticks import LTICKS_DECODED, tick_spread
from ...process.tradedvolume import traded_runner_vol
from ...process.prices import best_price
from ...feature.featureholder import FeatureHolder
from .featuresconfig import get_trend_feature_configs
from . import states as trendstates
from .datatypes import TrendData


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyTrendStrategy(MyFeatureStrategy):
    """
    Take breach of LTP min/max windows as drift in specific direction and back/lay in the direction of drift
    """

    def __init__(
            self,
            base_dir: str,
            criteria_kwargs: Dict,
            stake_size: float,
            hold_ms: int,
            min_hedge_price: float,
            feature_kwargs: Dict,
            *args,
            **kwargs):

        super().__init__('trend', base_dir, *args, **kwargs)
        self.criteria_kwargs = criteria_kwargs
        self.stake_size = stake_size
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
                        criteria_kwargs=self.criteria_kwargs,
                    ),
                    trendstates.TrendTradeStateOpenPlace(
                        stake_size=self.stake_size
                    ),
                    trendstates.TrendTradeStateOpenMatching(
                        hold_ms=self.hold_ms,
                    ),
                    basestates.TradeStateBin(),
                    basestates.TradeStatePending(),
                    basestates.TradeStateHedgeSelect(),
                    basestates.TradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price
                    ),
                    basestates.TradeStateHedgeWaitTake(),
                    basestates.TradeStateClean()
                ]
            },
            initial_state=basestates.TradeStateCreateTrade.name,
            selection_id=runner.selection_id,
        )

    def get_features_config(self) -> Dict:
        return self.features_config

    def market_initialisation(self, market: Market, market_book: MarketBook, feature_holder: FeatureHolder):
        self.trend_data_dicts[market.market_id] = dict()

    def runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
        self.trend_data_dicts[market_book.market_id][runner.selection_id] = TrendData(
            lay_gradient=0,
            lay_strength=0,
            back_gradient=0,
            back_strength=0,
            ltp_gradient=0,
            ltp_strength=0,
            best_back=0,
            best_lay=0,
            ladder_spread_ticks=0,
            ltp=0,
            smoothed_back=0,
            smoothed_lay=0,
            smoothed_ltp=0,
        )

    def trade_machine_kwargs(
            self,
            market: Market,
            market_book: MarketBook,
            runner_index: int,
    ) -> dict:

        runner = market_book.runners[runner_index]

        # get runner ID, trend data object and features dict
        selection_id = market_book.runners[runner_index].selection_id
        trend_data = self.trend_data_dicts[market_book.market_id][selection_id]
        features = self.feature_holders[market_book.market_id].features[selection_id]

        # set trend data attributes
        lay_regression = features['best lay smoothed'].sub_features['regression'].last_value() or {}
        back_regression = features['best back smoothed'].sub_features['regression'].last_value() or {}
        ltp_regression = features['ltp smoothed'].sub_features['regression'].last_value() or {}

        smoothed_back = features['best back smoothed'].last_value() or 0
        smoothed_lay = features['best lay smoothed'].last_value() or 0
        smoothed_ltp = features['ltp smoothed'].last_value() or 0

        trend_data.lay_gradient = lay_regression.get('gradient', 0)
        trend_data.lay_strength = lay_regression.get('rsquared', 0)
        trend_data.back_gradient = back_regression.get('gradient', 0)
        trend_data.back_strength = back_regression.get('rsquared', 0)
        trend_data.ltp_gradient = ltp_regression.get('gradient', 0)
        trend_data.ltp_strength = ltp_regression.get('rsquared', 0)
        trend_data.best_back = best_price(runner.ex.available_to_back)
        trend_data.best_lay = best_price(runner.ex.available_to_lay)
        trend_data.ltp = runner.last_price_traded or 0
        trend_data.ladder_spread_ticks = tick_spread(smoothed_back, smoothed_lay, check_values=False)
        trend_data.smoothed_back = smoothed_back
        trend_data.smoothed_lay = smoothed_lay
        trend_data.smoothed_ltp = smoothed_ltp

        return {
            'trend_data': trend_data
        }

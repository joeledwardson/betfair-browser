"""trade between LTP max/min windows"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
import logging

from ...strategy.trademachine import tradestates as basestates
from mytrading.strategy.trademachine.trademachine import RunnerStateMachine
from ...strategy.strategy import MyFeatureStrategy
from ...process import tick_spread, traded_runner_vol
from mytrading.strategy.feature import get_features_default_configs
from . import states as windowstates
from .tradetracker import WindowTradeTracker

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyWindowStrategy(MyFeatureStrategy):
    """
    Take breach of LTP min/max windows as drift in specific direction and back/lay in the direction of drift
    """

    def __init__(
            self,
            base_dir,
            stake_size,
            min_hedge_price,
            max_odds,
            ltp_min_spread,
            ltp_max_tick_delta,
            max_ladder_spread,
            track_seconds,
            min_total_matched,
            *args,
            **kwargs):

        super().__init__('ltp_window', base_dir, *args, **kwargs)
        self.stake_size = stake_size
        self.min_hedge_price = min_hedge_price
        self.max_odds = max_odds
        self.ltp_min_spread = ltp_min_spread
        self.ltp_max_tick_delta = ltp_max_tick_delta
        self.max_ladder_spread = max_ladder_spread
        self.track_seconds = track_seconds
        self.min_total_matched = min_total_matched

    def _trade_machine_create(
            self,
            runner: RunnerBook,
            mkt: Market,
            mbk: MarketBook
    ) -> RunnerStateMachine:
        """
        get trading state machine for selected runner
        """

        return RunnerStateMachine(
            states={
                state.name: state
                for state in [
                    basestates.TradeStateCreateTrade(),
                    windowstates.WindowTradeStateIdle(
                        max_odds=self.max_odds,
                        ltp_min_spread=self.ltp_min_spread,
                        ltp_max_tick_delta=self.ltp_max_tick_delta,
                        max_ladder_spread=self.max_ladder_spread,
                        track_seconds=self.track_seconds,
                        min_total_matched=self.min_total_matched,
                    ),
                    windowstates.WindowTradeStateOpenPlace(
                        stake_size=self.stake_size
                    ),
                    windowstates.WindowTradeStateOpenMatching(),
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

    def create_trade_tracker(
            self,
            runner: RunnerBook,
            market: Market,
            market_book: MarketBook,
            file_path) -> WindowTradeTracker:
        return WindowTradeTracker(
            selection_id=runner.selection_id,
            file_path=file_path
        )

    def get_features_config(self) -> Dict:

        # use default features but not regression
        features = get_features_default_configs()
        del features['best back regression']
        del features['best lay regression']
        return features

    def trade_machine_kwargs(
            self,
            market: Market,
            market_book: MarketBook,
            runner_index: int,
    ) -> dict:

        # get runner instance and dict of runner features
        runner = market_book.runners[runner_index]
        features = self.feature_holders[market.market_id].features[runner.selection_id]

        # get best back and lay from features, or 0 if
        best_back = features['best back'].last_value() or 0
        best_lay = features['best lay'].last_value() or 0

        # get back/lay spread, checking they are both valid odds
        ladder_spread = tick_spread(best_back, best_lay, check_values=True)

        # get LTP
        ltp = features['ltp'].last_value() or 0

        # get ltp previous value
        ltp_previous = features['ltp'].sub_features['previous value'].last_value() or 0

        return dict(
            ltp=ltp,
            ltp_previous=ltp_previous,
            ltp_min=features['ltp min'].last_value() or 0,
            ltp_max=features['ltp max'].last_value() or 0,
            best_back=best_back,
            best_lay=best_lay,
            ladder_spread=ladder_spread,
            total_matched=traded_runner_vol(runner),
        )

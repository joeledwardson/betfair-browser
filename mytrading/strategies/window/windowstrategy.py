"""trade between LTP max/min windows"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
from mytrading.trademachine import tradestates as basestates
from . import states as windowstates
from .tradetracker import WindowTradeTracker
from mytrading.trademachine.trademachine import RunnerStateMachine
from mytrading.strategy.featurestrategy import MyFeatureStrategy
from mytrading.process.ticks.ticks import LTICKS_DECODED
from mytrading.process.ladder import BfLadderPoint, get_ladder_point
from mytrading.feature.config import get_features_default_configs
import logging

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyWindowStrategy(MyFeatureStrategy):
    """
    Take breach of LTP min/max windows as drift in specific direction and back/lay in the direction of drift
    """

    def __init__(
            self,
            stake_size,
            min_hedge_price,
            max_odds,
            ltp_min_spread,
            max_ladder_spread,
            track_seconds,
            *args,
            **kwargs):

        super().__init__('ltp_window', *args, **kwargs)
        self.stake_size = stake_size
        self.min_hedge_price = min_hedge_price
        self.max_odds = max_odds
        self.ltp_min_spread = ltp_min_spread
        self.max_ladder_spread = max_ladder_spread
        self.track_seconds = track_seconds

    def create_state_machine(
            self,
            runner: RunnerBook,
            market: Market,
            market_book: MarketBook
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
                        max_ladder_spread=self.max_ladder_spread,
                        track_seconds=self.track_seconds
                    ),
                    windowstates.WindowTradeStateOpenPlace(
                        stake_size=self.stake_size
                    ),
                    windowstates.WindowTradeStateOpenMatching(),
                    basestates.TradeStateBin(),
                    basestates.TradeStatePending(),
                    basestates.TradeStateHedgeSelect(),
                    windowstates.WindowTradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price
                    ),
                    windowstates.WindowTradeStateHedgeTakeWait(),
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

    def get_features_config(self, runner: RunnerBook) -> Dict:
        # use default features but not regression
        features = get_features_default_configs()
        del features['best back regression']
        del features['best lay regression']
        return features

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:

        # update feature data (calls market_initialisation() if new market)
        self.strategy_process_market_book(market, market_book)

        # loop runners
        for runner_index, runner in enumerate(market_book.runners):

            trade_tracker = self.trade_trackers[market.market_id][runner.selection_id]
            state_machine = self.state_machines[market.market_id][runner.selection_id]
            features = self.feature_holders[market.market_id].features[runner.selection_id]

            if runner.selection_id == 28567519 and runner.last_price_traded == 3.25:
                my_breakpoint = True

            if self.process_trade_machine(runner, state_machine, trade_tracker):

                # get best back and lay from features, or 0 if
                best_back = features['best back'].last_value() or 0
                best_lay = features['best lay'].last_value() or 0
                ltp = features['ltp'].last_value() or 0
                ltp_min = features['ltp min'].last_value() or 0
                ltp_max = features['ltp max'].last_value() or 0

                if best_back in LTICKS_DECODED and best_lay in LTICKS_DECODED:
                    ladder_spread = LTICKS_DECODED.index(best_lay) - LTICKS_DECODED.index(best_back)
                else:
                    ladder_spread = 0

                state_machine.run(
                    market_book=market_book,
                    market=market,
                    runner_index=runner_index,
                    trade_tracker=trade_tracker,
                    strategy=self,
                    best_back=best_back,
                    best_lay=best_lay,
                    ltp=ltp,
                    ltp_min=ltp_min,
                    ltp_max=ltp_max,
                    ladder_spread=ladder_spread,
                )

            # update order tracker
            trade_tracker.update_order_tracker(market_book.publish_time)



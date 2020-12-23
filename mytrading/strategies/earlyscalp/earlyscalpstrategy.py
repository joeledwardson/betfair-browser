"""
Early scalping back to lay whilst there is sufficient spread between best back and lay
"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
import logging

from myutils.timing import timing_register
from ...trademachine import tradestates as basestates
from ...trademachine.trademachine import RunnerStateMachine
from ...strategy.featurestrategy import MyFeatureStrategy, MarketHandler
from ...process.ticks.ticks import LTICKS_DECODED, tick_spread
from ...process.tradedvolume import traded_runner_vol
from ...process.prices import best_price, get_ltps
from ...feature.featureholder import FeatureHolder
from .featuresconfig import get_scalp_feature_configs
from . import states as scalpstates
from .datatypes import EScalpData
from .tradetracker import EScalpTradeTracker


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyEarlyScalpStrategy(MyFeatureStrategy):
    """
    Trades spikes above & below LTP window max and minimums
    """

    def __init__(
            self,
            base_dir: str,
            stake_size: float,
            spread_min: int,
            scalp_cutoff_s: int,
            min_hedge_price: float,
            trade_transactions_cutoff: int,
            features_kwargs: dict,
            **kwargs
    ):

        super().__init__('early_scalp', base_dir, **kwargs)
        self.stake_size = stake_size
        self.spread_min = spread_min
        self.scalp_cutoff_s = scalp_cutoff_s
        self.min_hedge_price = min_hedge_price
        self.trade_transactions_cutoff = trade_transactions_cutoff

        # generate feature configuration dict
        self.features_config: dict = get_scalp_feature_configs(**features_kwargs)

        # market -> runner ID -> spike data
        self.scalp_data_dicts: Dict[str, Dict[int, EScalpData]] = dict()

    def create_trade_tracker(
            self,
            market: Market,
            market_book: MarketBook,
            runner: RunnerBook,
            file_path) -> EScalpTradeTracker:

        return EScalpTradeTracker(
            selection_id=runner.selection_id,
            file_path=file_path,
        )

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
                    scalpstates.EarlyScalpTradeStateIdle(
                        spread_min=self.spread_min,
                        scalp_cutoff_s=self.scalp_cutoff_s,
                        trade_transactions_cutoff=self.trade_transactions_cutoff,
                        next_state=scalpstates.EScalpStateTypes.ESCALP_STATE_BACK,
                    ),
                    scalpstates.EarlyScalpTradeStateBack(
                        stake_size=self.stake_size,
                        name=scalpstates.EScalpStateTypes.ESCALP_STATE_BACK,
                        next_state=basestates.TradeStateTypes.HEDGE_SELECT,
                    ),
                    basestates.TradeStateHedgeSelect(
                        next_state=scalpstates.EScalpStateTypes.ESCALP_STATE_HEDGE_PLACE,
                    ),
                    scalpstates.EarlyScalpTradeStateHedgePlace(
                        min_hedge_price=self.min_hedge_price,
                        name=scalpstates.EScalpStateTypes.ESCALP_STATE_HEDGE_PLACE,
                        next_state=scalpstates.EScalpStateTypes.ESCALP_STATE_HEDGE_WAIT,
                    ),
                    scalpstates.EarlyScalpTradeStateHedgePlace(
                        min_hedge_price=self.min_hedge_price,
                        name=scalpstates.EScalpStateTypes.ESCALP_STATE_HEDGE_WAIT,
                        next_state=basestates.TradeStateTypes.CLEANING,
                    ),
                    basestates.TradeStateBin(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStatePending(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStateClean(),
                    # basestates.TradeStateWait(
                    #     wait_ms=self.spike_wait_ms
                    # ),
                ]
            },
            initial_state=basestates.TradeStateCreateTrade.name,
            selection_id=runner.selection_id,
        )

    def get_features_config(self, market, market_book, runner_index) -> Dict:
        return self.features_config

    def custom_market_initialisation(self, market: Market, market_book: MarketBook):
        self.scalp_data_dicts[market.market_id] = dict()

    def custom_runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
        self.scalp_data_dicts[market_book.market_id][runner.selection_id] = EScalpData(
            back_delayed=0,
            lay_delayed=0,
            ltp=0,
            spread=0
        )

    def trade_machine_kwargs(
            self,
            market: Market,
            market_book: MarketBook,
            runner_index: int,
    ) -> dict:

        # get runner ID, trend data object and features dict
        selection_id = market_book.runners[runner_index].selection_id
        scalp_data = self.scalp_data_dicts[market_book.market_id][selection_id]
        features = self.market_handlers[market_book.market_id].runner_handlers[selection_id].features

        scalp_data.back_delayed = features['best back'].sub_features['hold_delay'].last_value()
        scalp_data.lay_delayed = features['best lay'].sub_features['hold_delay'].last_value()
        scalp_data.spread = features['spread'].last_value()
        scalp_data.ltp = features['ltp'].last_value()

        return {
            'data': scalp_data
        }

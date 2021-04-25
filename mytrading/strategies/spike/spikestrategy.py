"""
Trade based on back/lay/ltp trend using regression
"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
import logging

from myutils.myclass import store_kwargs
from ...strategy import tradestates as basestates
from ...strategy.trademachine import RunnerStateMachine
from ...strategy.strategy import MyFeatureStrategy
from ...process.prices import get_ltps
from .featuresconfig import get_spike_feature_configs
from . import states as spikestates
from .datatypes import SpikeData
from .tradetracker import SpikeTradeTracker


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MySpikeStrategy(MyFeatureStrategy):
    """
    Trades spikes above & below LTP window max and minimums
    """

    @store_kwargs(key_args='strategy_args', key_kwargs='strategy_kwargs')
    def __init__(
            self,
            trade_transactions_cutoff: int,
            stake_size: float,
            max_odds: float,
            min_hedge_price: float,
            window_spread_min: int,
            ladder_spread_max: int,
            tick_offset: int,
            tick_trigger: int,
            update_s: float,
            spike_wait_ms: int,
            hedge_tick_offset: int,
            hedge_hold_ms: int,
            features_kwargs: dict,
            enable_lay: bool,
            *args,
            **kwargs
    ):

        super().__init__(*args, **kwargs)
        self.trade_transactions_cutoff = trade_transactions_cutoff
        self.stake_size = stake_size
        self.max_odds = max_odds
        self.min_hedge_price = min_hedge_price
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max
        self.tick_offset = tick_offset
        self.tick_trigger = tick_trigger
        self.update_s = update_s
        self.spike_wait_ms = spike_wait_ms
        self.hedge_tick_offset = hedge_tick_offset
        self.hedge_hold_ms = hedge_hold_ms
        self.enable_lay = enable_lay

        # generate feature configuration dict
        self.features_config: dict = get_spike_feature_configs(**features_kwargs)

        # market -> runner ID -> spike data
        self.spike_data_dicts: Dict[str, Dict[int, SpikeData]] = dict()

    def create_trade_tracker(
            self,
            market: Market,
            market_book: MarketBook,
            runner: RunnerBook,
            file_path) -> SpikeTradeTracker:

        return SpikeTradeTracker(
            selection_id=runner.selection_id,
            file_path=file_path,
        )

    def get_state_machine(
            self,
            runner: RunnerBook,
            mkt: Market,
            mbk: MarketBook
    ) -> RunnerStateMachine:
        return RunnerStateMachine(
            states={
                state.name: state
                for state in [
                    basestates.TradeStateCreateTrade(),
                    spikestates.SpikeTradeStateIdle(
                        trade_transactions_cutoff=self.trade_transactions_cutoff,
                        max_odds=self.max_odds,
                        window_spread_min=self.window_spread_min,
                        ladder_spread_max=self.ladder_spread_max,
                        next_state=spikestates.SpikeStateTypes.SPIKE_STATE_MONITOR,
                    ),
                    spikestates.SpikeTradeStateMonitorWindows(
                        tick_offset=self.tick_offset,
                        tick_trigger=self.tick_trigger,
                        stake_size=self.stake_size,
                        window_spread_min=self.window_spread_min,
                        ladder_spread_max=self.ladder_spread_max,
                        update_s=self.update_s,
                        enable_lay=self.enable_lay,
                        name=spikestates.SpikeStateTypes.SPIKE_STATE_MONITOR,
                        next_state=[
                            basestates.TradeStateTypes.PENDING,
                            basestates.TradeStateTypes.WAIT,
                            basestates.TradeStateTypes.HEDGE_SELECT,
                        ]
                    ),
                    basestates.TradeStateWait(
                        wait_ms=self.spike_wait_ms,
                    ),
                    # spikestates.SpikeTradeStateBounce(
                    #     name=spikestates.SpikeStateTypes.SPIKE_STATE_BOUNCE,
                    #     wait_ms=self.spike_wait_ms,
                    # ),
                    basestates.TradeStateHedgeSelect(
                        next_state=basestates.TradeStateTypes.HEDGE_QUEUE_PLACE,
                    ),
                    basestates.TradeStateHedgePlaceQueue(
                        tick_offset=self.hedge_tick_offset,
                        min_hedge_price=self.min_hedge_price,
                    ),
                    basestates.TradeStateHedgeWaitQueue(
                        hold_time_ms=self.hedge_hold_ms,
                        hedge_place_state=basestates.TradeStateTypes.HEDGE_QUEUE_PLACE,
                    ),
                    basestates.TradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price,
                    ),
                    basestates.TradeStateHedgeWaitTake(
                        hedge_place_state=basestates.TradeStateTypes.HEDGE_TAKE_PLACE,
                    ),
                    # spikestates.SpikeTradeStateHedge(
                    #     name=spikestates.SpikeStateTypes.SPIKE_STATE_HEDGE,
                    #     next_state=spikestates.SpikeStateTypes.SPIKE_STATE_HEDGE_WAIT,
                    #     min_hedge_price=self.min_hedge_price,
                    # ),
                    # spikestates.SpikeTradeStateHedgeWait(
                    #     name=spikestates.SpikeStateTypes.SPIKE_STATE_HEDGE_WAIT,
                    #     next_state=basestates.TradeStateTypes.CLEANING,
                    # ),
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
        self.spike_data_dicts[market.market_id] = dict()

    def custom_runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
        self.spike_data_dicts[market_book.market_id][runner.selection_id] = SpikeData(
            best_back=0,
            best_lay=0,
            ltp=0,
            ltp_min=0,
            ltp_max=0,
        )

    def trade_machine_kwargs(
            self,
            market: Market,
            market_book: MarketBook,
            runner_index: int,
    ) -> dict:

        # get runner ID, trend data object and features dict
        selection_id = market_book.runners[runner_index].selection_id
        spike_data = self.spike_data_dicts[market_book.market_id][selection_id]
        features = self.market_handlers[market_book.market_id].runner_handlers[selection_id].features

        spike_data.best_back = features['best back'].last_value()
        spike_data.best_lay = features['best lay'].last_value()
        spike_data.ltp = features['ltp'].last_value()
        spike_data.ltp_min = features['ltp min'].last_value()
        spike_data.ltp_max = features['ltp max'].last_value()

        # get ID for shortest runner from LTPs
        ltps = get_ltps(market_book)
        first_id = next(iter(ltps.keys()), 0)

        return {
            'first_runner': first_id == selection_id,
            'spike_data': spike_data
        }

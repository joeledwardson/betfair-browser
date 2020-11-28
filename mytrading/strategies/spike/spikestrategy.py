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
from ...process.prices import best_price, get_ltps
from ...feature.featureholder import FeatureHolder
from .featuresconfig import get_spike_feature_configs
from . import states as spikestates
from .datatypes import SpikeData


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MySpikeStrategy(MyFeatureStrategy):
    """
    Trades spikes above & below LTP window max and minimums
    """

    def __init__(
            self,
            base_dir: str,
            stake_size: float,
            min_hedge_price: float,
            window_spread_min: int,
            ladder_spread_max: int,
            tick_offset: int,
            hedge_tick_offset: int,
            hedge_hold_ms: int,
            features_kwargs: dict,
            **kwargs
    ):

        super().__init__('spike', base_dir, **kwargs)
        self.stake_size = stake_size
        self.min_hedge_price = min_hedge_price
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max
        self.tick_offset = tick_offset
        self.hedge_tick_offset = hedge_tick_offset
        self.hedge_hold_ms = hedge_hold_ms

        # generate feature configuration dict
        self.features_config: dict = get_spike_feature_configs(**features_kwargs)

        # market -> runner ID -> spike data
        self.spike_data_dicts: Dict[str, Dict[int, SpikeData]] = dict()

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
                    spikestates.SpikeTradeStateIdle(
                        window_spread_min=self.window_spread_min,
                        ladder_spread_max=self.ladder_spread_max,
                        next_state=spikestates.SpikeStateTypes.SPIKE_STATE_MONITOR,
                    ),
                    spikestates.SpikeTradeStateMonitorWindows(
                        tick_offset=self.tick_offset,
                        stake_size=self.stake_size,
                        name=spikestates.SpikeStateTypes.SPIKE_STATE_MONITOR,
                        next_state=[
                            basestates.TradeStateTypes.PENDING,
                            basestates.TradeStateTypes.HEDGE_SELECT
                        ]
                    ),
                    basestates.TradeStateHedgeSelect(
                        next_state=basestates.TradeStateTypes.HEDGE_QUEUE_PLACE,
                    ),
                    basestates.TradeStateHedgePlaceQueue(
                        tick_offset=self.hedge_tick_offset,
                        min_hedge_price=self.min_hedge_price,
                    ),
                    basestates.TradeStateHedgeWaitQueue(
                        hold_time_ms=self.hedge_hold_ms,
                    ),
                    basestates.TradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price,
                    ),
                    basestates.TradeStateHedgeWaitTake(),
                    basestates.TradeStateBin(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStatePending(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStateClean()
                ]
            },
            initial_state=basestates.TradeStateCreateTrade.name,
            selection_id=runner.selection_id,
        )

    def get_features_config(self) -> Dict:
        return self.features_config

    def market_initialisation(self, market: Market, market_book: MarketBook, feature_holder: FeatureHolder):
        self.spike_data_dicts[market.market_id] = dict()

    def runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
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
        features = self.feature_holders[market_book.market_id].features[selection_id]

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

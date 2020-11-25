from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.order import OrderStatus, BetfairOrder
from flumine.order.ordertype import LimitOrder, OrderTypes

import logging
from enum import Enum
from typing import List, Dict, Union
from datetime import datetime, timedelta

from ...feature.features import RunnerFeatureBase
from ...tradetracker.tradetracker import TradeTracker
from ...process.side import select_ladder_side
from ...process.ticks.ticks import closest_tick
from ...tradetracker.messages import MessageTypes
from ...trademachine.tradestates import TradeStateTypes
from ...process.ticks.ticks import tick_spread
from ...trademachine import tradestates
from .tradetracker import SpikeTradeTracker
from .datatypes import SpikeData


MIN_BET_AMOUNT = 2
active_logger = logging.getLogger(__name__)


class SpikeTradeStateTypes(Enum):
    a=1


def bound_top(sd: SpikeData):
    return max(sd.ltp, sd.ltp_max, sd.best_back, sd.best_lay)


def bound_bottom(sd: SpikeData):
    return min(sd.ltp, sd.ltp_min, sd.best_back, sd.best_lay)


class SpikeTradeStateIdle(tradestates.TradeStateIdle):
    def __init__(
            self,
            tick_offset: int,
            window_spread_min: int,
            ladder_spread_max: int,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.tick_offset = tick_offset
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max

    def trade_criteria(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            first_runner: bool,
            spike_data: SpikeData,
            **inputs,
    ) -> bool:

        best_back = spike_data.best_back
        best_lay = spike_data.best_lay
        ltp = spike_data.ltp
        ltp_min = spike_data.ltp_min
        ltp_max = spike_data.ltp_max
        ladder_spread = spike_data.ladder_spread

        # check that all values are not None and non-zero
        if any([x is None or x == 0
                for x in [best_back, best_lay, ltp, ltp_min, ltp_max, ladder_spread]]):
            return False

        window_spread = tick_spread(ltp_min, ltp_max, check_values=False)

        if ladder_spread <= self.ladder_spread_max and window_spread >= self.window_spread_min:
            return True


class SpikeTradeStateMonitorWindows(tradestates.TradeStateBase):
    """
    place opening back/lay orders on entering, change if price moves and cancel & move to hedging if any of either
    trade is matched
    """


    def enter(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            first_runner: bool,
            spike_data: SpikeData,
            **inputs
    ):


    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: SpikeTradeTracker,
            strategy: BaseStrategy,
            first_runner: bool,
            spike_data: SpikeData,
            **inputs,
    ):
        if (
                not spike_data.best_lay or
                not spike_data.best_lay or
                not spike_data.ltp or
                not spike_data.ltp_min or
                not spike_data.ltp_max
        ):
            ERROR


        if trade_tracker.back_order.size_matched > 0 or trade_tracker.lay_order.size_matched > 0:
            trade_tracker.back_order.cancel(trade_tracker.back_order.size_remaining)
            trade_tracker.lay_order.cancel(trade_tracker.lay_order.size_remaining)
            # MOVE TO NEXT STATE

        top_value = bound_top(spike_data)
        top_tick = closest_tick(top_value, return_index=True)
        bottom_value = bound_bottom(spike_data)
        bottom_tick = closest_tick(bottom_value, return_index=True)



        if trade_tracker.back_order



        trade_tracker.back_order



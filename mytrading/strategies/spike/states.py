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
from ...process.ticks.ticks import tick_spread, LTICKS_DECODED
from ...trademachine import tradestates
from .tradetracker import SpikeTradeTracker
from .datatypes import SpikeData
from .messages import SpikeMessageTypes


MIN_BET_AMOUNT = 2
active_logger = logging.getLogger(__name__)


class SpikeStateTypes(Enum):
    SPIKE_STATE_MONITOR = 'monitor window orders'


def bound_top(sd: SpikeData):
    return max(sd.ltp, sd.ltp_max, sd.best_back, sd.best_lay)


def bound_bottom(sd: SpikeData):
    return min(sd.ltp, sd.ltp_min, sd.best_back, sd.best_lay)


class SpikeTradeStateIdle(tradestates.TradeStateIdle):
    def __init__(
            self,
            window_spread_min: int,
            ladder_spread_max: int,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max

    def trade_criteria(
            self,
            market_book: MarketBook,
            trade_tracker: TradeTracker,
            first_runner: bool,
            spike_data: SpikeData,
            **inputs,
    ) -> bool:

        best_back = spike_data.best_back
        best_lay = spike_data.best_lay
        ltp = spike_data.ltp
        ltp_min = spike_data.ltp_min
        ltp_max = spike_data.ltp_max

        # check that all values are not None and non-zero
        if (
            not best_back or
            not best_lay or
            not ltp or
            not ltp_min or
            not ltp_max
        ):
            return False

        window_spread = tick_spread(ltp_min, ltp_max, check_values=False)
        ladder_spread = tick_spread(best_back, best_lay, check_values=False)

        if ladder_spread <= self.ladder_spread_max and window_spread >= self.window_spread_min:
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_START,
                dt=market_book.publish_time,
                msg_attrs={
                    'best_back': best_back,
                    'best_lay': best_lay,
                    'ladder_spread': ladder_spread,
                    'ladder_spread_max': self.ladder_spread_max,
                    'ltp': ltp,
                    'ltp_max': ltp_max,
                    'ltp_min': ltp_min,
                    'window_spread': window_spread,
                    'window_spread_min': self.window_spread_min,
                },
                display_odds=ltp,
            )
            return True


class SpikeTradeStateMonitorWindows(tradestates.TradeStateBase):
    """
    place opening back/lay orders on entering, change if price moves and cancel & move to hedging if any of either
    trade is matched
    """
    def __init__(self, tick_offset: int, stake_size: float, **kwargs):
        super().__init__(**kwargs)
        self.tick_offset = tick_offset
        self.stake_size = stake_size
        self.entering = False

    def enter(self, trade_tracker: SpikeTradeTracker, **inputs):
        self.entering = True
        trade_tracker.back_order = None
        trade_tracker.lay_order = None

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            trade_tracker: SpikeTradeTracker,
            strategy: BaseStrategy,
            first_runner: bool,
            spike_data: SpikeData,
            **inputs,
    ):

        best_back = spike_data.best_back
        best_lay = spike_data.best_lay
        ltp = spike_data.ltp
        ltp_min = spike_data.ltp_min
        ltp_max = spike_data.ltp_max

        if (
                not best_back or
                not best_lay or
                not ltp or
                not ltp_min or
                not ltp_max
        ):
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_ENTER_FAIL,
                dt=market_book.publish_time,
                msg_attrs={
                    'best_back': best_back,
                    'best_lay': best_lay,
                    'ltp': ltp,
                    'ltp_max': ltp_max,
                    'ltp_min': ltp_min,
                }
            )
            return self.next_state

        if trade_tracker.back_order and trade_tracker.lay_order:
            if trade_tracker.back_order.size_matched > 0 or trade_tracker.lay_order.size_matched > 0:
                trade_tracker.back_order.cancel(trade_tracker.back_order.size_remaining)
                trade_tracker.lay_order.cancel(trade_tracker.lay_order.size_remaining)
                return self.next_state

        top_value = bound_top(spike_data)
        top_tick = closest_tick(top_value, return_index=True)
        top_tick = min(len(LTICKS_DECODED), top_tick + self.tick_offset)
        top_value = LTICKS_DECODED[top_tick]

        bottom_value = bound_bottom(spike_data)
        bottom_tick = closest_tick(bottom_value, return_index=True)
        bottom_tick = max(0, bottom_tick - self.tick_offset)
        bottom_value = LTICKS_DECODED[bottom_tick]

        if trade_tracker.back_order is None:
            trade_tracker.back_order = trade_tracker.active_trade.create_order(
                side='BACK',
                order_type=LimitOrder(
                    price=top_value,
                    size=self.stake_size
                )
            )
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_CREATE,
                dt=market_book.publish_time,
                msg_attrs={
                    'side': 'BACK',
                    'price': top_value,
                    'size': self.stake_size,
                },
                display_odds=top_value
            )
            strategy.place_order(market, trade_tracker.back_order)

        if trade_tracker.lay_order is None:
            trade_tracker.lay_order = trade_tracker.active_trade.create_order(
                side='LAY',
                order_type=LimitOrder(
                    price=bottom_value,
                    size=self.stake_size,
                )
            )
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_CREATE,
                dt=market_book.publish_time,
                msg_attrs={
                    'side': 'LAY',
                    'price': bottom_value,
                    'size': self.stake_size,
                },
                display_odds=bottom_value
            )
            strategy.place_order(market, trade_tracker.lay_order)

        if trade_tracker.back_order is not None and trade_tracker.back_order.status == OrderStatus.EXECUTABLE:
            back_price = trade_tracker.back_order.order_type.price
            if top_value != back_price:
                trade_tracker.log_update(
                    msg_type=SpikeMessageTypes.SPIKE_MSG_PRICE_REPLACE,
                    dt=market_book.publish_time,
                    msg_attrs={
                        'side': 'BACK',
                        'old_price': back_price,
                        'new_price': top_value
                    },
                    display_odds=top_value,
                )
                trade_tracker.back_order.cancel()
                trade_tracker.back_order = None

        if trade_tracker.lay_order is not None and trade_tracker.lay_order.status == OrderStatus.EXECUTABLE:
            lay_price = trade_tracker.lay_order.order_type.price
            if bottom_value != lay_price:
                trade_tracker.log_update(
                    msg_type=SpikeMessageTypes.SPIKE_MSG_PRICE_REPLACE,
                    dt=market_book.publish_time,
                    msg_attrs={
                        'side': 'LAY',
                        'old_price': lay_price,
                        'new_price': bottom_value
                    },
                    display_odds=bottom_value,
                )
                trade_tracker.lay_order.cancel()
                trade_tracker.lay_order = None





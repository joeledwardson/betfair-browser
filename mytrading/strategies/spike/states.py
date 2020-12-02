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
    SPIKE_STATE_BOUNCE = 'wait for bounce back'
    SPIKE_STATE_HEDGE = 'hedging'
    SPIKE_STATE_HEDGE_WAIT = 'waiting for hedge to complete'


def bound_top(sd: SpikeData):
    return max(sd.ltp, sd.ltp_max, sd.best_back, sd.best_lay)


def bound_bottom(sd: SpikeData):
    return min(sd.ltp, sd.ltp_min, sd.best_back, sd.best_lay)


def validate_spike_data(sd: SpikeData):
    return(
            sd.best_back and
            sd.best_lay and
            sd.ltp and
            sd.ltp_min and
            sd.ltp_max
    )


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
            trade_tracker: SpikeTradeTracker,
            first_runner: bool,
            spike_data: SpikeData,
            **inputs,
    ) -> bool:

        if not validate_spike_data(spike_data):
            return False

        window_spread = tick_spread(spike_data.ltp_min, spike_data.ltp_max, check_values=False)
        ladder_spread = tick_spread(spike_data.best_back, spike_data.best_lay, check_values=False)

        if ladder_spread <= self.ladder_spread_max and window_spread >= self.window_spread_min:
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_START,
                dt=market_book.publish_time,
                msg_attrs={
                    'best_back': spike_data.best_back,
                    'best_lay': spike_data.best_lay,
                    'ladder_spread': ladder_spread,
                    'ladder_spread_max': self.ladder_spread_max,
                    'ltp': spike_data.ltp,
                    'ltp_max': spike_data.ltp_max,
                    'ltp_min': spike_data.ltp_min,
                    'window_spread': window_spread,
                    'window_spread_min': self.window_spread_min,
                },
                display_odds=spike_data.ltp,
            )
            return True


class SpikeTradeStateMonitorWindows(tradestates.TradeStateBase):
    """
    place opening back/lay orders on entering, change if price moves and cancel & move to hedging if any of either
    trade is matched
    """
    def __init__(
            self,
            tick_offset: int,
            stake_size: float,
            ladder_spread_max: int,
            window_spread_min: int,
            update_hold_ms: int,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.tick_offset = tick_offset
        self.stake_size = stake_size
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max
        self.back_timestamp = datetime.now()
        self.lay_timestamp = datetime.now()
        self.update_hold_ms = update_hold_ms

    def enter(self, trade_tracker: SpikeTradeTracker, market_book: MarketBook, **inputs):
        trade_tracker.back_order = None
        trade_tracker.lay_order = None
        self.back_timestamp = market_book.publish_time
        self.lay_timestamp = market_book.publish_time

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

        # check back/lay/ltp values are all non-null
        if not validate_spike_data(spike_data):
            return [
                tradestates.TradeStateTypes.BIN,
                tradestates.TradeStateTypes.PENDING,
                tradestates.TradeStateTypes.IDLE,
            ]

        # compute max/min boundary values
        boundary_top_value = bound_top(spike_data)
        boundary_top_tick = closest_tick(boundary_top_value, return_index=True)
        top_tick = min(len(LTICKS_DECODED) - 1, boundary_top_tick + self.tick_offset)
        top_value = LTICKS_DECODED[top_tick]

        boundary_bottom_value = bound_bottom(spike_data)
        boundary_bottom_tick = closest_tick(boundary_bottom_value, return_index=True)
        bottom_tick = max(0, boundary_bottom_tick - self.tick_offset)
        bottom_value = LTICKS_DECODED[bottom_tick]

        # check if any money has been matched on either back or lay spike orders
        if trade_tracker.back_order and trade_tracker.lay_order:
            if trade_tracker.back_order.size_matched > 0 or trade_tracker.lay_order.size_matched > 0:

                # cancel remaining
                if trade_tracker.back_order.status == OrderStatus.EXECUTABLE:
                    trade_tracker.back_order.cancel(trade_tracker.back_order.size_remaining)
                if trade_tracker.lay_order.status == OrderStatus.EXECUTABLE:
                    trade_tracker.lay_order.cancel(trade_tracker.lay_order.size_remaining)

                # side side matched indicator for hedging state to read
                if trade_tracker.back_order.size_matched > 0:
                    trade_tracker.side_matched = 'BACK'
                else:
                    trade_tracker.side_matched = 'LAY'

                # set spike ltp for hedging state to read
                trade_tracker.spike_ltp = spike_data.ltp

                # record tick difference
                if trade_tracker.side_matched == 'BACK':
                    old_tick = trade_tracker.previous_max_index
                else:
                    old_tick = trade_tracker.previous_min_index

                ltp_tick = closest_tick(spike_data.ltp, return_index=True)
                tick_diff = ltp_tick - old_tick if old_tick else -1

                trade_tracker.log_update(
                    msg_type=SpikeMessageTypes.SPIKE_MSG_BREACHED,
                    dt=market_book.publish_time,
                    msg_attrs={
                        'side': trade_tracker.side_matched,
                        'old_price': LTICKS_DECODED[old_tick],
                        'ltp': spike_data.ltp,
                        'spike_ticks': tick_diff
                    }
                )

                return self.next_state

        window_spread = tick_spread(spike_data.ltp_min, spike_data.ltp_max, check_values=False)
        ladder_spread = tick_spread(spike_data.best_back, spike_data.best_lay, check_values=False)

        # check back/lay spread is still within tolerance and ltp min/max spread is above tolerance
        if not(ladder_spread <= self.ladder_spread_max and window_spread >= self.window_spread_min):
            return [
                tradestates.TradeStateTypes.BIN,
                tradestates.TradeStateTypes.PENDING,
                tradestates.TradeStateTypes.IDLE,
            ]


        # create back order if doesn't exist
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

        # create lay order if doesn't exist
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

        # check back order valid
        if trade_tracker.back_order is not None and trade_tracker.back_order.status == OrderStatus.EXECUTABLE:

            # check back price moved
            back_price = trade_tracker.back_order.order_type.price
            back_proceed = False

            # check if upper boundary value is less than current order
            if top_value < back_price:

                # proceed if value is less than current order price for set amount of time
                if (market_book.publish_time - self.back_timestamp) >= timedelta(milliseconds=self.update_hold_ms):
                    back_proceed = True
            else:
                # if value is not below current order price reset timestamp
                self.back_timestamp = market_book.publish_time

                # if upper boundary value is more than current order price then move immediately
                if top_value > back_price:
                    back_proceed = True

            if back_proceed:
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

                # cancel back order and clear for re-creation
                trade_tracker.back_order.cancel()
                trade_tracker.back_order = None

        # check lay order valid
        if trade_tracker.lay_order is not None and trade_tracker.lay_order.status == OrderStatus.EXECUTABLE:

            # check if lay price moved
            lay_price = trade_tracker.lay_order.order_type.price
            lay_proceed = False

            if bottom_value > lay_price:
                if (market_book.publish_time - self.lay_timestamp) >= timedelta(milliseconds=self.update_hold_ms):
                    lay_proceed = True
            else:
                self.lay_timestamp = market_book.publish_time
                if bottom_value < lay_price:
                    lay_proceed = True

            if lay_proceed:
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

                # cancel lay order and clear for re-creation
                trade_tracker.lay_order.cancel()
                trade_tracker.lay_order = None

        # update previous state boundary max/mins
        trade_tracker.previous_min_index = boundary_bottom_tick
        trade_tracker.previous_max_index = boundary_top_tick


def get_window_price(side, spike_data: SpikeData):
    if side == 'BACK':
        price = spike_data.ltp_min
        return closest_tick(price, return_index=False, round_down=True)
    else:
        price = spike_data.ltp_max
        return closest_tick(price, return_index=False, round_up=True)


class SpikeTradeStateHedge(tradestates.TradeStateHedgePlaceBase):
    def get_hedge_price(
            self,
            trade_tracker: SpikeTradeTracker,
            spike_data: SpikeData,
            **inputs
    ) -> float:
        return get_window_price('BACK' if trade_tracker.side_matched == 'LAY' else 'LAY', spike_data)


class SpikeTradeStateHedgeWait(tradestates.TradeStateHedgeWaitBase):
    def price_moved(
            self,
            trade_tracker: SpikeTradeTracker,
            spike_data: SpikeData,
            **inputs
    ) -> float:
        return get_window_price('BACK' if trade_tracker.side_matched == 'LAY' else 'LAY', spike_data)


class SpikeTradeStateBounce(tradestates.TradeStateWait):
    def run(
            self,
            market_book: MarketBook,
            trade_tracker: SpikeTradeTracker,
            spike_data: SpikeData,
            **inputs
    ):
        if (market_book.publish_time - self.start_time) >= self.td:
            return True
        elif not validate_spike_data(spike_data):
            return True
        elif trade_tracker.side_matched == 'LAY' and spike_data.best_back > trade_tracker.spike_ltp:
            return True
        elif trade_tracker.side_matched == 'BACK' and spike_data.best_lay < trade_tracker.spike_ltp:
            return True






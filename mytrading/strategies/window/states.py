from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.ordertype import LimitOrder, OrderTypes

from typing import Dict, List
import logging
from datetime import datetime
from enum import Enum

from ...process.prices import best_price
from ...process.side import select_ladder_side, select_operator_side, invert_side
from ...tradetracker.messages import MessageTypes
from ...trademachine.tradestates import TradeStateTypes
from ...process.ticks.ticks import closest_tick
from ...trademachine import tradestates
from .tradetracker import WindowTradeTracker
from .messages import WindowMessageTypes

active_logger = logging.getLogger(__name__)


class WindowTradeStateTypes(Enum):

    WINDOW_HEDGE_PLACE = 'window - placing hedge at optimal price'
    WINDOW_HEDGE_WAIT = 'window - waiting for hedge to match'



def window_bail(ltp, ltp_min, ltp_max, up):
    """
    assuming a trade going in 'up' (True=up, False=down), return True if ltp has reversed and breached the
    opposite window boundary
    """
    return (up and ltp < ltp_min) or (not up and ltp > ltp_max)


def get_price(ltp, ladder, side):
    """
    get the best price
    - max of LTP, back
    - min of LTP, lay
    """

    ltp = ltp or 0
    price = best_price(ladder)

    # if greening on back side, take max of LTP and best back
    if side == 'BACK':
        price = price or 0
        return max(ltp, price)

    # if greening on lay side, take min of LTP and best lay
    else:
        price = price or 1000
        return min(ltp, price)


class WindowTradeStateIdle(tradestates.TradeStateIdle):
    """
    Override idle state whereby on successful breach of ltp window max/min, trade tracker is set with `direction_up`
    indicator and advance to next state
    """

    def __init__(self, max_odds, ltp_min_spread, max_ladder_spread, track_seconds, min_total_matched, **kwargs):
        super().__init__(**kwargs)

        self.min_total_matched: float = min_total_matched
        self.track_seconds = track_seconds
        self.max_odds = max_odds
        self.ltp_min_spread: int = ltp_min_spread
        self.max_ladder_spread: int = max_ladder_spread

        self.up: bool = True
        self.tracker_start: datetime = datetime.now()
        self.tracking: bool = False

        self.ltp = 0
        self.window_value = 0
        self.ladder_spread = 0
        self.total_matched = 0
        self.ltp_spread = 0

    def enter(self, **kwargs):
        """
        When entering IDLE state make sure window tracking has been cleared
        """
        self.tracking = False

    def validate(self, ltp: float, ltp_spread: int, ladder_spread: int, total_matched: float) -> bool:
        """
        validate if a LTP has breached ltp min/max window values, ltp min/max have sufficient spread, and back/lay
        ladder spread is within maximum spread
        """
        if ltp <= self.max_odds:
            if ltp_spread >= self.ltp_min_spread:
                if ladder_spread <= self.max_ladder_spread and ladder_spread != 0:
                    if total_matched >= self.min_total_matched:
                        return True
        return False

    def track_msg_attrs(self, direction_up: bool) -> dict:
        """
        get tracking message attrs dictionary

        Returns
        -------

        """
        return {
            'direction_up': direction_up,
            'ltp': self.ltp,
            'ltp_max': self.max_odds,
            'window_value': self.window_value,
            'window_spread': self.ltp_spread,
            'window_spread_min': self.ltp_min_spread,
            'ladder_spread': self.ladder_spread,
            'ladder_spread_max': self.max_ladder_spread,
            'total_matched': self.total_matched or 0,
            'min_total_matched': self.min_total_matched,
        }

    def track_start(
            self,
            dt: datetime,
            trade_tracker: WindowTradeTracker,
            direction_up: bool,
    ):
        """
        begin tracking a breach of LTP min/max window
        - 'direction_up'=True means breach of LTP max
        - 'direction_up'=False means breach of LTP min
        """
        self.tracking = True
        self.up = direction_up
        self.tracker_start = dt
        trade_tracker.direction_up = direction_up

        trade_tracker.log_update(
            msg_type=WindowMessageTypes.WDW_MSG_TRACK_START,
            msg_attrs=self.track_msg_attrs(direction_up),
            dt=dt,
            display_odds=self.ltp,
        )

    def track_stop(
            self,
            dt: datetime,
            trade_tracker: WindowTradeTracker,
    ):
        """
        stop an active track
        """
        self.tracking = False

        trade_tracker.log_update(
            msg_type=WindowMessageTypes.WDW_MSG_TRACK_FAIL,
            msg_attrs=self.track_msg_attrs(self.up),
            dt=dt,
            display_odds=self.ltp,
        )

    def get_ltp_spread(self, ltp_max, ltp_min) -> int:
        """
        get tick spread between ltp max and min
        """
        index_min = closest_tick(ltp_min, return_index=True)
        index_max = closest_tick(ltp_max, return_index=True)
        return index_max - index_min


    def run(
            self,
            market_book: MarketBook,
            trade_tracker: WindowTradeTracker,
            ltp: float,
            ltp_min: float,
            ltp_max: float,
            best_back: float,
            best_lay: float,
            ladder_spread: int,
            total_matched: float,
            **inputs,
    ):
        dt = market_book.publish_time

        # first check there is money available to back and lay and money has been traded
        if not best_back or not best_lay or not ltp:
            return

        # get LTP spread
        self.ltp_spread = self.get_ltp_spread(ltp_max, ltp_min)

        # assign inputs to state variables
        self.ladder_spread = ladder_spread
        self.total_matched = total_matched
        self.ltp = ltp

        start = False
        stop = False
        done = False
        up = False

        # check if broken upper window
        if ltp > ltp_max:

            self.window_value = ltp_max
            up = True

            # if not tracking, start
            if not self.tracking:
                if self.validate(ltp, self.ltp_spread, ladder_spread, total_matched):
                    start = True

            else:

                # already tracking and in right direction
                if self.up:

                    # check that still meets validation
                    if self.validate(ltp, self.ltp_spread, ladder_spread, total_matched):

                        # check for completion time
                        if (dt - self.tracker_start).total_seconds() >= self.track_seconds:

                            done = True

                    # validation failed
                    else:

                        stop = True

                # tracking down instead of up, switch direction
                else:

                    self.window_value = ltp_min
                    stop = True

        # check if broken lower window
        elif ltp < ltp_min:

            self.window_value = ltp_min
            up = False

            # if not tracking, start
            if not self.tracking:
                if self.validate(ltp, self.ltp_spread, ladder_spread, total_matched):
                    start = True

            else:

                # already tracking and in right direction, check for completion of time limit
                if not self.up:

                    # check for validation
                    if self.validate(ltp, self.ltp_spread, ladder_spread, total_matched):

                        # check for time completion
                        if (dt - self.tracker_start).total_seconds() >= self.track_seconds:

                            done = True

                    # validation failed
                    else:

                        stop = True

                # tracking up instead of down, switch direction
                else:

                    self.window_value = ltp_max
                    stop = True

        # if here reached then have not broken upper/lower window
        else:

            # get window value from direction
            if self.up:
                self.window_value = ltp_max
            else:
                self.window_value = ltp_min

            # if tracking then stop
            if self.tracking:

                stop = True

        if stop:

            # stop active track of window breach
            self.track_stop(dt=dt, trade_tracker=trade_tracker)

        elif start:

            # start tracking window breach
            self.track_start(dt=dt, trade_tracker=trade_tracker, direction_up=up)

        elif done:

            # completed window breach, use trade tracker direction for log
            trade_tracker.log_update(
                msg_type=WindowMessageTypes.WDW_MSG_TRACK_SUCCESS,
                msg_attrs=self.track_msg_attrs(trade_tracker.direction_up),
                dt=dt
            )

            return self.next_state


class WindowTradeStateOpenPlace(tradestates.TradeStateOpenPlace):

    def __init__(self, stake_size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stake_size = stake_size

    def place_order(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WindowTradeTracker,
            strategy: BaseStrategy,
            ltp: float,
            ltp_min: float,
            ltp_max: float,
            best_back: float,
            best_lay: float,
            **inputs):

        if ltp_min < ltp < ltp_max:
            trade_tracker.log_update(
                msg_type=WindowMessageTypes.WDW_MSG_LTP_FAIL,
                msg_attrs={
                    'ltp': ltp,
                    'ltp_min': ltp_min,
                    'ltp_max': ltp_max,
                },
                dt=market_book.publish_time
            )
            return None

        if trade_tracker.direction_up:

            # breached LTP max, pick lowest value from ltp and best lay available
            side = 'LAY'
            price = min(best_lay, ltp)

            # abort if no lay information
            if best_lay == 0:
                trade_tracker.log_update(
                    msg_type=WindowMessageTypes.WDW_MSG_LAY_INVALID,
                    dt=market_book.publish_time
                )
                return None

        else:

            # breached LTP min, pick highest value from ltp and best back available
            side = 'BACK'
            price = max(best_back, ltp)

            # abort if no back information
            if best_back == 0:
                trade_tracker.log_update(
                    msg_type=WindowMessageTypes.WDW_MSG_BACK_INVALID,
                    dt=market_book.publish_time
                )
                return None

        # get already matched size
        matched = sum([o.size_matched for o in trade_tracker.active_trade.orders if
                       o.order_type.ORDER_TYPE==OrderTypes.LIMIT])

        stake_size = self.stake_size
        if matched:
            stake_size = stake_size - matched
            if stake_size <= 0:
                trade_tracker.log_update(
                    msg_type=WindowMessageTypes.WDW_MSG_STK_INVALID,
                    msg_attrs={
                        'start_stake_size': self.stake_size,
                        'matched': matched,
                        'stake_size': stake_size,
                    },
                    dt=market_book.publish_time
                )
                return None

        # round to 2dp
        stake_size = round(stake_size, ndigits=2)
        price = round(price, ndigits=2)

        # create and place order
        order = trade_tracker.active_trade.create_order(
            side=side,
            order_type=LimitOrder(
                price=price,
                size=stake_size
            ))
        strategy.place_order(market, order)
        return order


class WindowTradeStateOpenMatching(tradestates.TradeStateOpenMatching):

    # return new state(s) if different action required, otherwise None
    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WindowTradeTracker,
            strategy: BaseStrategy,
            ltp: float,
            ltp_min: float,
            ltp_max: float,
            **inputs
    ):
        price = trade_tracker.active_order.order_type.price
        up = trade_tracker.direction_up

        sts = trade_tracker.active_order.status

        # if error detected then bail
        if sts in tradestates.order_error_states:
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_OPEN_ERROR,
                msg_attrs={
                    'order_status': str(sts),
                },
                dt=market_book.publish_time
            )
            return TradeStateTypes.CLEANING

        # check if breached opposite window
        if window_bail(ltp, ltp_min, ltp_max, up):

            # if fail window breached is opposite to direction, ltp min for laying, ltp max for backing
            window_value = ltp_min if up else ltp_max

            trade_tracker.log_update(
                msg_type=WindowMessageTypes.WDW_MSG_DIR_CHANGE,
                msg_attrs={
                    'direction_up': up,
                    'ltp': ltp,
                    'window_value': window_value
                },
                dt=market_book.publish_time,
                display_odds=ltp,
            )

            return [
                TradeStateTypes.BIN,
                TradeStateTypes.PENDING,
                TradeStateTypes.HEDGE_SELECT
            ]

        # check if not fully matched
        elif sts != OrderStatus.EXECUTION_COMPLETE:

            # get ladder on close side for hedging
            available = select_ladder_side(
                market_book.runners[runner_index].ex,
                trade_tracker.active_order.side
            )

            # get LTP/back/lay price
            price_available = get_price(ltp, available, trade_tracker.active_order.side)

            # check if price has drifted since placement of open order
            if (up and price_available > price) or (not up and price_available < price):
                trade_tracker.log_update(
                    msg_type=WindowMessageTypes.WDW_MSG_PLACE_DRIFT,
                    msg_attrs={
                        'direction_up': up,
                        'old_ltp': price,
                        'ltp': ltp,
                    },
                    dt=market_book.publish_time
                )
                return [
                    TradeStateTypes.BIN,
                    TradeStateTypes.PENDING,
                    TradeStateTypes.OPEN_PLACING
                ]


# class WindowTradeStateHedgePlaceTake(tradestates.TradeStateHedgePlaceBase):
#     """take the best price available from either ltp or best back/lay for hedging"""
#
#     def get_hedge_price(
#             self,
#             open_ladder: List[Dict],
#             close_ladder: List[Dict],
#             close_side,
#             trade_tracker: WindowTradeTracker,
#             market_book: MarketBook,
#             market: Market,
#             runner_index: int,
#             strategy: BaseStrategy,
#             ltp,
#             **inputs
#     ):
#         return get_price(ltp, close_ladder, close_side)
#
#
# class WindowTradeStateHedgeTakeWait(tradestates.TradeStateHedgeWaitBase):
#
#     def price_moved(
#             self,
#             market_book: MarketBook,
#             market: Market,
#             runner_index: int,
#             trade_tracker: WindowTradeTracker,
#             strategy: BaseStrategy,
#             ltp,
#             **inputs
#     ) -> float:
#
#         order = trade_tracker.active_order
#
#         # get ladder on close side for hedging
#         available = select_ladder_side(
#             market_book.runners[runner_index].ex,
#             order.side
#         )
#
#         # get LTP/back/lay price
#         price = get_price(ltp, available, order.side)
#
#         # if on back side, and new price is smaller than active green price then change
#         if order.side == 'BACK':
#             if price < order.order_type.price:
#                 return price
#
#         # if on lay side, and new price is larger than active green price then change
#         else:
#             if price > order.order_type.price:
#                 return price
#
#         return 0

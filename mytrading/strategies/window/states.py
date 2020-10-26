from datetime import datetime
from mytrading.trademachine.tradestates import TradeStateTypes
from mytrading.process.ticks.ticks import closest_tick
from mytrading.trademachine import tradestates
from .tradetracker import WindowTradeTracker
from .messages import WindowMessageTypes
import logging
from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.ordertype import LimitOrder, OrderTypes
from mytrading.tradetracker.messages import MessageTypes
from typing import Dict, List
from mytrading.process.prices import best_price
from mytrading.strategy.side import select_ladder_side, select_operator_side, invert_side

active_logger = logging.getLogger(__name__)


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
    price = best_price(ladder) or 0

    # if greening on back side, take max of LTP and best back
    if side == 'BACK':
        return max(ltp, price)

    # if greening on lay side, take min of LTP and best lay
    else:
        return min(ltp, price)


class WindowTradeStateIdle(tradestates.TradeStateIdle):

    def __init__(self, max_odds, ltp_min_spread, max_ladder_spread, track_seconds, **kwargs):
        super().__init__(**kwargs)

        self.track_seconds = track_seconds
        self.max_odds = max_odds
        self.ltp_min_spread: int = ltp_min_spread
        self.max_ladder_spread: int = max_ladder_spread

        self.up: bool = True
        self.tracker_start: datetime = datetime.now()
        self.tracking: bool = False

    def validate(self, ltp: float, ltp_spread: int, ladder_spread: int) -> bool:
        """
        validate if a LTP has breached ltp min/max window values, ltp min/max have sufficient spread, and back/lay
        ladder spread is within maximum spread
        """
        if ltp <= self.max_odds:
            if ltp_spread >= self.ltp_min_spread:
                if ladder_spread <= self.max_ladder_spread and ladder_spread != 0:
                    return True
        return False

    def track_start(
            self,
            dt: datetime,
            trade_tracker: WindowTradeTracker,
            ltp,
            direction_up: bool,
            window_value,
            window_spread,
            ladder_spread,
    ):
        """
        begin tracking a breach of LTP min/max window
        - 'direction_up'=True means breach of LTP max
        - 'direction_up'=False means breach of LTP min
        """
        self.tracking = True
        self.up = direction_up
        self.tracker_start = dt

        trade_tracker.log_update(
            msg_type=WindowMessageTypes.TRACK_START,
            msg_attrs={
                'direction_up': direction_up,
                'ltp': ltp,
                'ltp_max': self.max_odds,
                'window_value': window_value,
                'window_spread': window_spread,
                'window_spread_min': self.ltp_min_spread,
                'ladder_spread': ladder_spread,
                'ladder_spread_max': self.max_ladder_spread
            },
            dt=dt,
            display_odds=ltp,
        )

    def track_stop(
            self,
            dt: datetime,
            trade_tracker: WindowTradeTracker,
            ltp,
            window_value,
            window_spread,
            ladder_spread,
    ):
        """
        stop an active track
        """
        self.tracking = False

        trade_tracker.log_update(
            msg_type=WindowMessageTypes.TRACK_FAIL,
            msg_attrs={
                'direction_up': self.up,
                'ltp': ltp,
                'ltp_max': self.max_odds,
                'window_value': window_value,
                'window_spread': window_spread,
                'window_spread_min': self.ltp_min_spread,
                'ladder_spread': ladder_spread,
                'ladder_spread_max': self.max_ladder_spread
            },
            dt=dt,
            display_odds=ltp,
        )

    def get_ltp_spread(self, ltp_max, ltp_min) -> int:
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
            **inputs,
    ):
        dt = market_book.publish_time

        # first check there is money available to back and lay and money has been traded
        if not best_back or not best_lay or not ltp:
            return

        # get LTP spread
        ltp_spread = self.get_ltp_spread(ltp_max, ltp_min)

        start = False
        stop = False
        done = False
        up = False
        window_value = 0

        # check if broken upper window
        if ltp > ltp_max:

            window_value = ltp_max
            up = True

            # if not tracking, start
            if not self.tracking:
                if self.validate(ltp, ltp_spread, ladder_spread):
                    start = True

            else:

                # already tracking and in right direction
                if self.up:

                    # check that still meets validation
                    if self.validate(ltp, ltp_spread, ladder_spread):

                        # check for completion time
                        if (dt - self.tracker_start).total_seconds() >= self.track_seconds:

                            done = True

                    # validation failed
                    else:

                        stop = True

                # tracking down instead of up, switch direction
                else:

                    window_value = ltp_min
                    stop = True

        # check if broken lower window
        elif ltp < ltp_min:

            window_value = ltp_min
            up = False

            # if not tracking, start
            if not self.tracking:
                if self.validate(ltp, ltp_spread, ladder_spread):
                    start = True

            else:

                # already tracking and in right direction, check for completion of time limit
                if not self.up:

                    # check for validation
                    if self.validate(ltp, ltp_spread, ladder_spread):

                        # check for time completion
                        if (dt - self.tracker_start).total_seconds() >= self.track_seconds:

                            done = True

                    # validation failed
                    else:

                        stop = True

                # tracking up instead of down, switch direction
                else:

                    window_value = ltp_max
                    stop = True

        # if here reached then have not broken upper/lower window
        else:

            # get window value from direction
            if self.up:
                window_value = ltp_max
            else:
                window_value = ltp_min

            # if tracking then stop
            if self.tracking:

                stop = True

        if stop:

            self.track_stop(
                dt=dt,
                trade_tracker=trade_tracker,
                ltp=ltp,
                window_value=window_value,
                window_spread=ltp_spread,
                ladder_spread=ladder_spread
            )

        elif start:

            self.track_start(
                dt=dt,
                trade_tracker=trade_tracker,
                ltp=ltp,
                direction_up=up,
                window_value=window_value,
                window_spread=ltp_spread,
                ladder_spread=ladder_spread
            )

        elif done:

            trade_tracker.log_update(
                msg_type=WindowMessageTypes.TRACK_SUCCESS,
                msg_attrs={
                    'direction_up': True
                },
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
                msg_type=WindowMessageTypes.OPEN_PLACE_FAIL,
                msg_attrs={
                    'reason': 'ltp not breached bounds'
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
                    msg_type=WindowMessageTypes.OPEN_PLACE_FAIL,
                    msg_attrs={
                        'reason': 'best lay invalid'
                    },
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
                    msg_type=WindowMessageTypes.OPEN_PLACE_FAIL,
                    msg_attrs={
                        'reason': 'best back invalid'
                    },
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
                    msg_type=WindowMessageTypes.OPEN_PLACE_FAIL,
                    msg_attrs={
                        'reason': 'stake size invalid'
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
                msg_type=MessageTypes.OPEN_ERROR,
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
                msg_type=WindowMessageTypes.DIRECTION_CHANGE,
                msg_attrs={
                    'direction_up': up,
                    'ltp': ltp,
                    'window_value': window_value
                },
                dt=market_book.publish_time
            )

            return [
                TradeStateTypes.BIN,
                TradeStateTypes.HEDGE_SELECT
            ]

        # check if not fully matched
        elif sts != OrderStatus.EXECUTION_COMPLETE:

            # check if price has drifted since placement of open order
            if (up and ltp > price) or (not up and ltp < price):
                trade_tracker.log_update(
                    msg_type=WindowMessageTypes.PLACE_DRIFT,
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


class WindowTradeStateHedgePlaceTake(tradestates.TradeStateHedgePlaceTake):
    """take the best price available from either ltp or best back/lay for hedging"""

    def get_hedge_price(
            self,
            open_ladder: List[Dict],
            close_ladder: List[Dict],
            close_side,
            trade_tracker: WindowTradeTracker,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            strategy: BaseStrategy,
            ltp,
            **inputs
    ):
        return get_price(ltp, close_ladder, close_side)


class WindowTradeStateHedgeTakeWait(tradestates.TradeStateHedgeTakeWait):

    def price_moved(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WindowTradeTracker,
            strategy: BaseStrategy,
            ltp,
            **inputs
    ) -> float:

        order = trade_tracker.active_order

        # get ladder on close side for hedging
        available = select_ladder_side(
            market_book.runners[runner_index].ex,
            order.side
        )

        # get LTP/back/lay price
        price = get_price(ltp, available, order.side)

        # if on back side, and new price is smaller than active green price then change
        if order.side == 'BACK':
            if price < order.order_type.price:
                return price

        # if on lay side, and new price is larger than active green price then change
        else:
            if price > order.order_type.price:
                return price

        return 0

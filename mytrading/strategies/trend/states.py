from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.order import OrderStatus, BetfairOrder
from flumine.order.ordertype import LimitOrder, OrderTypes

import logging
from enum import Enum
from typing import List, Dict, Union
from datetime import datetime, timedelta

from ...process.side import select_ladder_side
from ...tradetracker.messages import MessageTypes
from ...trademachine.tradestates import TradeStateTypes
from ...process.ticks.ticks import tick_spread
from ...trademachine import tradestates
from .tradetracker import TrendTradeTracker
from .datatypes import TrendData, TrendCriteria
from .messages import TrendMessageTypes

MIN_BET_AMOUNT = 2
active_logger = logging.getLogger(__name__)


class TrendTradeStateTypes(Enum):
    a=1


class TrendTradeStateIdle(tradestates.TradeStateIdle):
    def __init__(
            self,
            criteria_kwargs: dict,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.criteria = TrendCriteria(**criteria_kwargs)

    def trade_criteria(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TrendTradeTracker,
            strategy: BaseStrategy,
            **inputs,
    ) -> bool:
        dt = market_book.publish_time
        trend_data: TrendData = inputs['trend_data']
        proceed = False

        if all([
            abs(trend_data.lay_gradient) >= self.criteria.ladder_gradient_min,
            abs(trend_data.back_gradient) >= self.criteria.ladder_gradient_min,
            abs(trend_data.ltp_gradient) >= self.criteria.ltp_gradient_min,
            trend_data.lay_strength >= self.criteria.ladder_strength_min,
            trend_data.back_strength >= self.criteria.ladder_strength_min,
            trend_data.ltp_strength >= self.criteria.ltp_strength_min,
            trend_data.ladder_spread_ticks <= self.criteria.ladder_spread_max
        ]):

            if all([
                trend_data.lay_gradient > 0,
                trend_data.back_gradient > 0,
                trend_data.ltp_gradient > 0,
            ]):
                trade_tracker.direction_up = False
                proceed = True

            if all([
                trend_data.lay_gradient < 0,
                trend_data.back_gradient < 0,
                trend_data.ltp_gradient < 0,
            ]):
                trade_tracker.direction_up = True
                proceed = True

        if proceed:
            trade_tracker.log_update(
                msg_type=TrendMessageTypes.TREND_MSG_START,
                dt=dt,
                msg_attrs={
                    'trend_data': trend_data.__dict__,
                    'criteria': self.criteria.__dict__,
                    'direction_up': trade_tracker.direction_up,
                },
                display_odds=trend_data.smoothed_ltp
            )
            return True


class TrendTradeStateOpenPlace(tradestates.TradeStateOpenPlace):

    def __init__(self, stake_size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stake_size = stake_size

    def place_order(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TrendTradeTracker,
            strategy: BaseStrategy,
            **inputs) -> Union[None, BetfairOrder]:

        dt = market_book.publish_time

        if trade_tracker.direction_up:

            # trend is upwards (odds getting bigger), queue using back side of book
            atb = market_book.runners[runner_index].ex.available_to_back

            # check not empty
            if len(atb) == 0:
                trade_tracker.log_update(
                    msg_type=MessageTypes.MSG_BACK_EMPTY,
                    dt=dt,
                )
                return None

            else:
                side = 'LAY'
                price = atb[0]['price']

        else:

            # trend is downwards (odds getting smaller), queue using lay side of book
            atl = market_book.runners[runner_index].ex.available_to_lay

            if len(atl) == 0:
                trade_tracker.log_update(
                    msg_type=MessageTypes.MSG_LAY_EMPTY,
                    dt=dt,
                )
                return None
            else:
                side = 'BACK'
                price = atl[0]['price']

        # get already matched size
        matched = sum([o.size_matched for o in trade_tracker.active_trade.orders if
                       o.order_type.ORDER_TYPE==OrderTypes.LIMIT])

        # get base stake size
        stake_size = self.stake_size

        # get remaining stake size
        remaining = stake_size - matched

        # dont bet below minimum - TODO update with constant
        if remaining < MIN_BET_AMOUNT:
            return None

        # round to 2dp
        stake_size = round(remaining, ndigits=2)
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


class TrendTradeStateOpenMatching(tradestates.TradeStateOpenMatching):

    def __init__(self, hold_ms: int, *args, **kwargs):
        super().__init__(move_on_complete=False, *args, **kwargs)
        self.price_changed = False
        self.change_timestamp: datetime = None
        self.hold_ms = hold_ms
        self.move_hold_time = timedelta(milliseconds=hold_ms)

    def enter(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TrendTradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        self.price_changed = False

    def get_trend_reverse(self, trade_tracker: TrendTradeTracker, trend_data: TrendData) -> bool:

        if all([
            trade_tracker.direction_up,
            trend_data.back_gradient > 0,
            trend_data.lay_gradient > 0,
        ]):
            return True

        elif all([
            not trade_tracker.direction_up,
            trend_data.back_gradient < 0,
            trend_data.lay_gradient < 0,
        ]):
            return True

        else:
            return False

    def process_price_spike(self, dt: datetime, trade_tracker: TrendTradeTracker, new_price: float):

        self.price_changed = True
        self.change_timestamp = dt
        trade_tracker.log_update(
            msg_type=TrendMessageTypes.TREND_MSG_PRICE_SPIKE,
            dt=dt,
            msg_attrs={
                'direction_up': trade_tracker.direction_up,
                'order_price': trade_tracker.active_order.order_type.price,
                'new_price': new_price
            },
            display_odds=new_price
        )

    def process_price_change(self, dt: datetime, trade_tracker: TrendTradeTracker) -> List[Enum]:
        trade_tracker.log_update(
            msg_type=TrendMessageTypes.TREND_MSG_PRICE_MOVE,
            dt=dt,
            msg_attrs={
                'direction_up': trade_tracker.direction_up,
                'order_price': trade_tracker.active_order.order_type.price,
                'hold_ms': self.hold_ms
            }
        )
        return [
            TradeStateTypes.BIN,
            TradeStateTypes.PENDING,
            TradeStateTypes.OPEN_PLACING
        ]

    def open_order_processing(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TrendTradeTracker,
            strategy: BaseStrategy,
            **inputs
    ) -> Union[None, List[Enum]]:

        dt = market_book.publish_time
        trend_data: TrendData = inputs['trend_data']
        trend_reverse = self.get_trend_reverse(trade_tracker, trend_data)

        if trend_reverse:
            trade_tracker.log_update(
                msg_type=TrendMessageTypes.TREND_MSG_REVERSE,
                dt=dt,
                msg_attrs={
                    'trend_data': trend_data.__dict__,
                    'direction_up': trade_tracker.direction_up,
                },
                display_odds=trend_data.smoothed_ltp,
            )
            return [
                TradeStateTypes.BIN,
                TradeStateTypes.PENDING,
                TradeStateTypes.HEDGE_SELECT
            ]

        # check order actually exists
        if trade_tracker.active_order is None:
            return

        # check order not fully matched
        if trade_tracker.active_order.status == OrderStatus.EXECUTION_COMPLETE:
            return

        # get active order price
        order_price = trade_tracker.active_order.order_type.price

        def process_breach(new_price: float):

            # check for price change
            if not self.price_changed:

                # new price change detected
                self.process_price_spike(dt, trade_tracker, new_price)

            else:

                # price change continues
                if self.change_timestamp and dt > (self.change_timestamp + self.move_hold_time):

                    # price move hold criteria met, move to new price
                    return self.process_price_change(dt, trade_tracker)

            return None

        # check for price breach if trend down
        if trade_tracker.direction_up == False and trend_data.best_lay < order_price:
            return process_breach(trend_data.best_lay)

        # check for price breach if trend up
        elif trade_tracker.direction_up == True and trend_data.best_back > order_price:
            return process_breach(trend_data.best_back)

        else:
            # no price breach detected
            self.price_changed = False


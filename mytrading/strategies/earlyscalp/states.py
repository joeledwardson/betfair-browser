from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.ordertype import LimitOrder, OrderTypes
from flumine.order.trade import TradeStatus

import logging
from enum import Enum

from mytrading.strategy.tradetracker.messages import MessageTypes
from ...process.ticks.ticks import LTICKS_DECODED
from ...strategy.trademachine import tradestates
from .tradetracker import EScalpTradeTracker
from .datatypes import EScalpData
from .messages import EScalpMessageTypes


MIN_BET_AMOUNT = 2
active_logger = logging.getLogger(__name__)


class EScalpStateTypes(Enum):
    ESCALP_STATE_BACK = 'place opening BACK trade'
    ESCALP_STATE_HEDGE_PLACE = 'place scalp hedge trade'
    ESCALP_STATE_HEDGE_WAIT = 'waiting for scalp hedge trade'


class EarlyScalpTradeStateIdle(tradestates.TradeStateIdle):
    def __init__(
            self,
            spread_min: int,
            scalp_cutoff_s: int,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.spread_min = spread_min
        self.scalp_cutoff_s = scalp_cutoff_s
        self.cutoff_previous_state = False

    def trade_criteria(
            self,
            market: Market,
            market_book: MarketBook,
            trade_tracker: EScalpTradeTracker,
            data: EScalpData,
            **inputs,
    ) -> bool:

        if not self.cutoff_previous_state:
            seconds_to_start = (market_book.market_definition.market_time - market_book.publish_time).total_seconds()
            if seconds_to_start <= self.scalp_cutoff_s:
                self.cutoff_previous_state = True
                trade_tracker.log_update(
                    msg_type=EScalpMessageTypes.ESCALP_MSG_STOP,
                    dt=market_book.publish_time,
                    msg_attrs={
                        'cutoff_s': self.scalp_cutoff_s,
                    }
                )

        if self.cutoff_previous_state:
            return False

        if not data.back_delayed or not data.lay_delayed or not data.spread:
            return False

        if not data.allow:
            return False

        if data.spread >= self.spread_min:
            trade_tracker.log_update(
                msg_type=EScalpMessageTypes.ESCALP_MSG_START,
                dt=market_book.publish_time,
                msg_attrs={
                    'spread': data.spread,
                    'spread_min': self.spread_min,
                },
                display_odds=data.back_delayed,
            )
            return True


class EarlyScalpTradeStateBack(tradestates.TradeStateBase):
    def __init__(self, stake_size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stake_size = stake_size

    def enter(self, trade_tracker: EScalpTradeTracker, market_book: MarketBook, **inputs):
        trade_tracker.back_order = None
        trade_tracker.lay_order = None

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: EScalpTradeTracker,
            strategy: BaseStrategy,
            data: EScalpData,
            **inputs
    ):

        if not data.allow:
            return [
                tradestates.TradeStateTypes.BIN,
                tradestates.TradeStateTypes.HEDGE_TAKE_PLACE,
            ]

        tt = trade_tracker

        if data.lay_delayed not in LTICKS_DECODED or data.back_delayed not in LTICKS_DECODED:
            if data.lay_delayed not in LTICKS_DECODED:
                price = data.lay_delayed
            else:
                price = data.back_delayed
            tt.log_update(
                msg_type=MessageTypes.MSG_PRICE_INVALID,
                dt=market_book.publish_time,
                msg_attrs={
                    'price': price,
                }
            )
            return [
                tradestates.TradeStateTypes.BIN,
                tradestates.TradeStateTypes.HEDGE_SELECT,
            ]

        back_matched = sum([
            o.size_matched > 0 for o in tt.active_trade.orders
            if o.order_type.ORDER_TYPE == OrderTypes.LIMIT and o.side == 'BACK'
        ])
        lay_matched = sum([
            o.size_matched > 0 for o in tt.active_trade.orders
            if o.order_type.ORDER_TYPE == OrderTypes.LIMIT and o.side == 'LAY'
        ])

        if (back_matched/self.stake_size) > 0.9 and (lay_matched/self.stake_size) > 0.9:
            return self.next_state
        #
        # if any([
        #     o.size_matched > 0 for o in tt.active_trade.orders
        #     if o.order_type.ORDER_TYPE == OrderTypes.LIMIT and o.side == 'BACK'
        # ]):
        #     if tt.back_order and tt.back_order.size_remaining:
        #         strategy.cancel_order(market, tt.back_order)

        if not tt.back_order:
            # TODO (temporary fix so that orders are processed)
            size = self.stake_size - back_matched
            if size > 0:
                tt.active_trade._update_status(TradeStatus.PENDING)
                tt.back_order = tt.active_trade.create_order(
                    side='BACK',
                    order_type=LimitOrder(
                        price=data.lay_delayed,
                        size=size
                    ))
                strategy.place_order(market, tt.back_order)

        if tt.back_order is not None:
            if tt.back_order.order_type.price != data.lay_delayed:
                if tt.back_order.size_remaining >= 2:
                    strategy.cancel_order(market, tt.back_order)
                    tt.back_order = None

        if not tt.lay_order:
            # TODO (temporary fix so that orders are processed)
            size = self.stake_size - lay_matched
            if size > 0:
                tt.active_trade._update_status(TradeStatus.PENDING)
                tt.lay_order = tt.active_trade.create_order(
                    side='LAY',
                    order_type=LimitOrder(
                        price=data.back_delayed,
                        size=size
                    ))
                strategy.place_order(market, tt.lay_order)

        if tt.lay_order is not None:
            if tt.lay_order.order_type.price != data.back_delayed:
                if tt.lay_order.size_remaining >= 2:
                    strategy.cancel_order(market, tt.lay_order)
                    tt.lay_order = None


class EarlyScalpTradeStateHedgePlace(tradestates.TradeStateHedgePlaceBase):
    def get_hedge_price(self, data: EScalpData, **inputs) -> float:
        return data.back_delayed


class EarlyScalpTradeStateHedgeWait(tradestates.TradeStateHedgeWaitBase):
    def price_moved(self, data: EScalpData, **inputs):
        return data.back_delayed

    def run(self, data: EScalpData, **inputs):
        return_states = super().run(data=data, **inputs)
        if not data.allow:
            return [
                tradestates.TradeStateTypes.BIN,
                tradestates.TradeStateTypes.HEDGE_TAKE_PLACE,
            ]
        else:
            return return_states


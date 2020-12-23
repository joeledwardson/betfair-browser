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
        self.past_cutoff = False

    def trade_criteria(
            self,
            market: Market,
            market_book: MarketBook,
            trade_tracker: EScalpTradeTracker,
            first_runner: bool,
            data: EScalpData,
            **inputs,
    ) -> bool:

        if not self.past_cutoff:
            seconds_to_start = (market_book.market_definition.market_time - market_book.publish_time).total_seconds()
            if seconds_to_start <= self.scalp_cutoff_s:
                self.past_cutoff = True
                trade_tracker.log_update(
                    msg_type=EScalpMessageTypes.ESCALP_MSG_STOP,
                    dt=market_book.publish_time,
                    msg_attrs={
                        'cutoff_s': self.scalp_cutoff_s,
                    }
                )

        if self.past_cutoff:
            return False

        if not data.back_delayed or not data.lay_delayed or not data.spread:
            return False

        if data.spread >= self.spread_min:
            trade_tracker.log_update(
                msg_type=EScalpMessageTypes.SPIKE_MSG_START,
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
        tt = trade_tracker

        if data.lay_delayed not in LTICKS_DECODED:
            tt.log_update(
                msg_type=MessageTypes.MSG_PRICE_INVALID,
                dt=market_book.publish_time,
                msg_attrs={
                    'price': data.lay_delayed,
                }
            )
            return [
                tradestates.TradeStateTypes.BIN,
                tradestates.TradeStateTypes.HEDGE_SELECT,
            ]

        if any([
            o.size_matched > 0 for o in tt.active_trade.orders
            if o.order_type.ORDER_TYPE == OrderTypes.LIMIT and o.side == 'BACK'
        ]):
            if tt.back_order and tt.back_order.size_remaining:
                strategy.cancel_order(market, tt.back_order)
            return self.next_state

        if not tt.back_order:
            tt.back_order = tt.active_trade.create_order(
                side='BACK',
                order_type=LimitOrder(
                    price=data.lay_delayed,
                    size=self.stake_size
                ))
            strategy.place_order(market, tt.back_order)

        if tt.back_order:
            if tt.back_order.order_type.price != data.lay_delayed:
                strategy.cancel_order(market, tt.back_order)
                tt.back_order = None


class EarlyScalpTradeStateHedgePlace(tradestates.TradeStateHedgePlaceBase):
    def get_hedge_price(self, data: EScalpData, **inputs) -> float:
        return data.back_delayed


class EarlyScalpTradeStateHedgeWait(tradestates.TradeStateHedgeWaitBase):
    def price_moved(self, data: EScalpData, **inputs):
        return data.back_delayed



from flumine import FlumineBacktest, clients, BaseStrategy
from flumine.order.order import BaseOrder, BetfairOrder, OrderStatus
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue
from betfairlightweight import APIClient

import json
from myutils import betting, bf_feature, bf_window, statemachine as stm, bf_utils as bfu
import os
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import statistics
import statsmodels.api as sm
import operator
from enum import Enum
from dataclasses import dataclass, field

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

order_error_states = [
    OrderStatus.EXPIRED,
    OrderStatus.VOIDED,
    OrderStatus.LAPSED,
    OrderStatus.VIOLATION
]

order_pending_states = [
    OrderStatus.PENDING,
    OrderStatus.CANCELLING,
    OrderStatus.UPDATING,
    OrderStatus.REPLACING
]


@dataclass
class TradeTracker:

    selection_id: str
    active_trade: Trade = field(default=None)
    active_order: BetfairOrder = field(default=None)
    open_side: str = field(default=None)
    previous_order_status: OrderStatus = field(default=None)
    _log : List[Dict] = field(default_factory=list)

    def log(self, msg: str, dt: datetime, level=logging.INFO):
        active_logger.log(level, f'{dt} "{self.selection_id}": {msg}')
        self._log.append({
            'dt': dt,
            'msg': msg
        })


class TradeStates(Enum):
    BASE =              'unimplemented'
    IDLE =              'unplaced'
    OPEN_PLACING =      'placing opening trade'
    OPEN_MATCHING =     'waiting for opening trade to match'
    OPEN_ERROR =        'trade has experienced an error'
    BIN =               'bottling trade'
    # BIN_WAITING =       'waiting for bottle to complete'
    HEDGE_SELECT =      'selecting type of hedge'
    HEDGE_PLACE_TAKE =  'place hedge trade at available pirce'
    HEDGE_TAKE_MATCHING='waiting for hedge to match at available price'
    # HEDGE_MATCHING =    'waiting hedge match'
    # HEDGE_CANCEL =      'cancelling hedge trade'
    # HEDGE_ERROR =       'hedge trade encountered an error'
    CLEANING =          'cleaning trade'
    PENDING =           'pending state'


class RunnerStateMachine(stm.StateMachine):
    def __init__(self, states: Dict[Enum, stm.State], initial_state: Enum, selection_id: str):
        super().__init__(states, initial_state)
        self.selection_id = selection_id

    def process_state_change(self, old_state, new_state):
        active_logger.info(f'runner "{self.selection_id}" has changed from state "{old_state}" to "{new_state}"')
        if new_state == TradeStates.PENDING:
            my_debug_breakpoint = True

# base trading state for implementing sub-classes with run() defined
class TradeStateBase(stm.State):

    # override default state name and next state without the need for sub-class
    def __init__(self, name: TradeStates = None, next_state: TradeStates = None):
        if name:
            self.name = name
        if next_state:
            self.next_state = next_state

    # use enumerations for name of state for other states to refer to
    name: TradeStates = TradeStates.BASE

    # easily overridable state to progress to when state action is complete
    next_state: TradeStates = TradeStates.BASE

    # called to operate state, options for return are:
    # - return None to remain in same state
    # - return TradeStates enum for new state
    # - return list of [TradeStates] for list of new states
    # - return True to continue in list of states queued
    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        raise NotImplementedError

    def __str__(self):
        return f'Trade state: {self.name}'


# intermediary state for waiting for trade to process
class TradeStatePending(TradeStateBase):

    name = TradeStates.PENDING

    # called to operate state - return None to remain in same state, or return string for new state
    def run(self, trade_tracker: TradeTracker, **inputs):
        if trade_tracker.active_order.status not in order_pending_states:
            return True


# idle state, waiting to open trade, need to implemeneting sub-classes trade_criteria()
class TradeStateIdle(TradeStateBase):

    name = TradeStates.IDLE
    next_state = TradeStates.OPEN_PLACING

    # return true to move to next state opening trade, false to remain idle
    def trade_criteria(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs) -> bool:
        raise NotImplementedError

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        if self.trade_criteria(market_book, market, runner_index, trade_tracker, strategy, **inputs):
            return self.next_state


# place an opening trade
class TradeStateOpenPlace(TradeStateBase):
    name = TradeStates.OPEN_PLACING
    next_state = TradeStates.OPEN_MATCHING

    def place_trade(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs) -> BetfairOrder:
        raise NotImplementedError

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        limit_order = self.place_trade(market_book, market, runner_index, trade_tracker, strategy, **inputs)
        if not limit_order:
            return TradeStates.CLEANING
        else:
            trade_tracker.active_trade = limit_order.trade
            trade_tracker.active_order = limit_order
            trade_tracker.open_side = limit_order.side
            return [TradeStates.PENDING, self.next_state]


# wait for open trade to match
class TradeStateOpenMatching(TradeStateBase):

    name = TradeStates.OPEN_MATCHING
    # don't bother with 'next_state' as too many different paths from this state

    # return new state(s) if different action required, otherwise None
    def open_trade_processing(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        raise NotImplementedError

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        new_states = self.open_trade_processing(market_book, market, runner_index, trade_tracker, strategy, **inputs)
        if new_states:
            return new_states
        else:
            sts = trade_tracker.active_order.status

            # if sts == OrderStatus.EXECUTABLE:
            #     return TradeStates.OPEN_PARTIAL

            if sts == OrderStatus.EXECUTION_COMPLETE:
                return TradeStates.HEDGE_SELECT

            elif sts == OrderStatus.LAPSED or sts == OrderStatus.EXPIRED:
                return TradeStates.CLEANING

            elif sts == OrderStatus.VOIDED or sts == OrderStatus.VIOLATION:
                return TradeStates.OPEN_ERROR


# bin (cancel) active trade
class TradeStateBin(TradeStateBase):

    name = TradeStates.BIN

    def run(
            self,
            trade_tracker: TradeTracker,
            **inputs
    ):
        sts = trade_tracker.active_order.status

        if sts in order_pending_states:
            # still pending
            return None

        elif sts == OrderStatus.EXECUTABLE:
            # partial match, cancel() checks for EXECUTABLE state when this when called
            trade_tracker.active_order.cancel(trade_tracker.active_order.size_remaining)
            return True

        else:
            # order complete/failed, can exit
            return True


# # wait for cancel to complete - if any matched then hedge
# class TradeStateBinWait(TradeStateBase):
#
#     name = TradeStates.BIN_WAITING
#     next_state = TradeStates.CLEANING
#
#     def run(
#             self,
#             market_book: MarketBook,
#             market: Market,
#             runner_index: int,
#             trade_tracker: TradeTracker,
#             strategy: BaseStrategy,
#             **inputs
#     ):
#         sts = trade_tracker.active_order.status
#
#         if sts in order_pending_states:
#             # cancel pending
#             return
#         elif sts == OrderStatus.EXECUTABLE or sts == OrderStatus.EXECUTION_COMPLETE:
#             if trade_tracker.active_order.size_matched:
#                 # money matched while binning, need to hedge
#                 return TradeStates.HEDGE_SELECT
#             else:
#                 # order cancelled and no money match, can exit
#                 return self.next_state
#         else:
#             # error state
#             return TradeStates.OPEN_ERROR
#


# select hedge type - chooses default 'self.next_state' unless 'hedge_state' found in 'inputs' kwargs
class TradeStateHedgeSelect(TradeStateBase):

    name = TradeStates.HEDGE_SELECT
    next_state = TradeStates.HEDGE_PLACE_TAKE

    def run(self, **inputs):
        return inputs.get('hedge_state', self.next_state)


# place hedge at available price
class TradeStateHedgePlaceTake(TradeStateBase):

    name = TradeStates.HEDGE_PLACE_TAKE
    next_state = TradeStates.HEDGE_TAKE_MATCHING

    def __init__(self, min_hedge_price, name: TradeStates = None, next_state: TradeStates = None):
        super().__init__(name, next_state)
        self.min_hedge_price = min_hedge_price

    # get the difference in selection win profit vs selection loss profit (i.e. offset from perfect green)
    def get_outstanding_profit(self, trade: Trade):
        back_stakes = sum([o.size_matched for o in trade.orders if o.side == 'BACK'])
        back_profits = sum([
            (o.average_price_matched - 1) * (o.size_matched) for o in trade.orders
            if o.status == OrderStatus.EXECUTABLE or o.status == OrderStatus.EXECUTION_COMPLETE
            and o.side == 'BACK' and o.average_price_matched and o.size_matched
        ])

        lay_stakes = sum([o.size_matched for o in trade.orders if o.side == 'LAY'])
        lay_exposure = sum([
            (o.average_price_matched - 1) * (o.size_matched) for o in trade.orders
            if o.status == OrderStatus.EXECUTABLE or o.status == OrderStatus.EXECUTION_COMPLETE
            and o.side == 'LAY' and o.average_price_matched and o.size_matched
        ])

        # selection win profit is (back bet profits - lay bet exposures)
        # selection loss profit is (lay stakes - back stakes)
        # return seleciton win profit - seleciton loss profit
        return (back_profits - lay_exposure) - (lay_stakes - back_stakes)


    # take best available price - i.e. if trade was opened as a back (the 'open_side') argument, then take lowest lay
    # price available (the 'close_side')
    def get_hedge_price(
            self,
            open_ladder: List[Dict],
            close_ladder: List[Dict],
            close_side,
            trade_tracker: TradeTracker
    ):
        if close_ladder:
            return close_ladder[0]['price']
        else:
            return trade_tracker.active_order.order_type.price

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):

        outstanding_profit = self.get_outstanding_profit(trade_tracker.active_trade)
        if abs(outstanding_profit) <= self.min_hedge_price:
            trade_tracker.log(
                f'win/loss diff £{outstanding_profit} doesnt exceed required hedge amount £{self.min_hedge_price}',
                market_book.publish_time
            )
            return TradeStates.CLEANING

        runner = market_book.runners[runner_index]

        if outstanding_profit > 0:
            # value is positive: trade is "underlayed", i.e. needs more lay money

            close_side = 'LAY'
            open_ladder = runner.ex.available_to_back
            close_ladder = runner.ex.available_to_lay

        else:
            # value is negative: trade is "overlayed", i.e. needs more back moneyy

            close_side = 'BACK'
            open_ladder = runner.ex.available_to_lay
            close_ladder = runner.ex.available_to_back

        if not open_ladder or not close_ladder:
            trade_tracker.log('one side of book is completely empty...', market_book.publish_time)
            return TradeStates.CLEANING

        green_price = self.get_hedge_price(open_ladder, close_ladder, close_side, trade_tracker)
        green_size = round(abs(outstanding_profit) / (green_price - 1), 2)

        trade_tracker.log(
            f'greening active order on {green_size} for £{green_price:.2f}',
            market_book.publish_time
        )
        green_order = trade_tracker.active_trade.create_order(
            side=close_side,
            order_type=LimitOrder(
                price=green_price,
                size=green_size
            ))
        strategy.place_order(market, green_order)

        trade_tracker.active_order = green_order
        return [TradeStates.PENDING, self.next_state]


# wait for hedge at available price to complete - if price moves before complete, adjust price to match
# a known disadvantage of this is if the price drifts massively, it will not account for the drop in stake required
class TradeStateHedgeTakeWait(TradeStateBase):

    name = TradeStates.HEDGE_TAKE_MATCHING
    next_state = TradeStates.CLEANING

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):

        order = trade_tracker.active_order

        # if there has been an error with the order, try to hedge again
        if order.status in order_error_states:
            trade_tracker.log(
                f'error trying to hedge: "{order.status}, retrying...',
                market_book.publish_time
            )
            return TradeStates.HEDGE_PLACE_TAKE
        elif order.status == OrderStatus.EXECUTION_COMPLETE:
            return self.next_state
        elif order.status not in order_pending_states:
            # get ladder on close side for hedging
            available = bfu.select_ladder_side(
                market_book.runners[runner_index].ex,
                order.side
            )
            # get operator for comparing available price and current hedge price
            op = bfu.select_operator_side(
                order.side,
                invert=True
            )
            # if current price is not the same as order price then move
            if available and op(available[0]['price'], order.order_type.price):
                trade_tracker.log(
                    f'moving hedge price from {order.order_type.price} to {available[0]["price"]}',
                    market_book.publish_time
                )
                order.replace(available[0]['price'])


# TODO - implement
class TradeStateClean(TradeStateBase):

    name = TradeStates.CLEANING

    def run(self, **kwargs):
        pass

# # queue hedge
# class TradeStateHedgePlaceQueue(TradeStateHedgePlaceTake):
#
#     name = TradeStates.HEDGE_PLACE_TAKE
#     next_state = TradeStates.HEDGE_MATCHING
#
#     # queue hedge on the other side of the book. i.e. if trade was opened as a back 'open_ladder' is back,
#     # then want to queue our lay on the back side (as low as possible), rather than taking the availble lay price
#     def get_hedge_price(
#             self,
#             open_ladder: List[Dict],
#             close_ladder: List[Dict],
#             close_side,
#             trade_tracker: TradeTracker
#     ):
#         if close_ladder:
#             return open_ladder[0]['price']
#         else:
#             return trade_tracker.active_order.order_type.price
#
#
# # wait for hedge to complete
# class TradeStateHedgeWait(TradeStateBase):
#
#     def trade_hedge_processing(
#             self,
#             market_book: MarketBook,
#             market: Market,
#             runner_index: int,
#             trade_tracker: TradeTracker,
#             strategy: BaseStrategy,
#             **inputs
#     ):
#         raise NotImplementedError
#
#     def run(
#             self, trade_tracker: TradeTracker, **inputs
#     ):
#         if trade_tracker.active_order.status == OrderStatus.EXECUTION_COMPLETE:
#             return TradeStates.CLEANING
#         return self.trade_hedge_processing(trade_tracker=trade_tracker, **inputs)
#
#

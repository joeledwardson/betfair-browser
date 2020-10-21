from flumine import BaseStrategy
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook

from myutils import statemachine as stm
from mytrading.strategy.side import select_ladder_side, select_operator_side
from mytrading.process.match_bet import get_match_bet_sums
from mytrading.tradetracker.tradetracker import TradeTracker

import logging
from typing import List, Dict
from enum import Enum

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
    # OrderStatus.CANCELLING, # never leaves cancelling state
    OrderStatus.UPDATING,
    OrderStatus.REPLACING
]


class TradeStates(Enum):
    """
    Enumeration of trade state keys used for names in state instances
    """

    BASE =              'unimplemented'
    CREATE_TRADE =      'create trade'
    IDLE =              'unplaced'
    OPEN_PLACING =      'placing opening trade'
    OPEN_MATCHING =     'waiting for opening trade to match'
    OPEN_ERROR =        'trade has experienced an error'
    BIN =               'bottling trade'
    HEDGE_SELECT =      'selecting type of hedge'
    HEDGE_PLACE_TAKE =  'place hedge trade at available price'
    HEDGE_TAKE_MATCHING='waiting for hedge to match at available price'
    CLEANING =          'cleaning trade'
    PENDING =           'pending state'


class RunnerStateMachine(stm.StateMachine):
    """
    implement state machine for runners, logging state changes with runner ID
    """
    def __init__(self, states: Dict[Enum, stm.State], initial_state: Enum, selection_id: int):
        super().__init__(states, initial_state)
        self.selection_id = selection_id

    def process_state_change(self, old_state, new_state):
        active_logger.info(f'runner "{self.selection_id}" has changed from state "{old_state}" to "{new_state}"')
        if new_state == TradeStates.PENDING:
            my_debug_breakpoint = True


class TradeStateBase(stm.State):
    """
    base trading state for implementing sub-classes with run() defined
    """

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

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        """
         called to operate state, options for return are:
         - return None to remain in same state
         - return TradeStates enum for new state
         - return list of [TradeStates] for list of new states
         - return True to continue in list of states queued
        """
        raise NotImplementedError

    def __str__(self):
        return f'Trade state: {self.name}'


class TradeStatePending(TradeStateBase):
    """
    intermediary state for waiting for trade to process
    intermediary state: run() returns True when complete
    """

    name = TradeStates.PENDING

    # called to operate state - return None to remain in same state, or return string for new state
    def run(self, trade_tracker: TradeTracker, **inputs):

        # check order exists
        if trade_tracker.active_order is None:
            return True

        if trade_tracker.active_order.status not in order_pending_states:
            return True


class TradeStateCreateTrade(TradeStateBase):
    """
    Create trade instance and move to next state
    """
    name = TradeStates.CREATE_TRADE
    next_state = TradeStates.IDLE

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        trade = Trade(
            market_id=market.market_id,
            selection_id=market_book.runners[runner_index].selection_id,
            handicap=market_book.runners[runner_index].handicap,
            strategy=strategy
        )
        trade_tracker.trades.append(trade)
        trade_tracker.active_trade = trade
        return self.next_state


class TradeStateIdle(TradeStateBase):
    """
    idle state, waiting to open trade as specified by implementing in sub-classes trade_criteria() function
    Once trade_criteria() returns True, will move to next state
    """
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


class TradeStateOpenPlace(TradeStateBase):
    """
    place an opening trade
    """
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
            trade_tracker.active_order = limit_order
            trade_tracker.open_side = limit_order.side
            return [TradeStates.PENDING, self.next_state]


class TradeStateOpenMatching(TradeStateBase):
    """
    wait for open trade to match
    """
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


class TradeStateBin(TradeStateBase):

    """
    intermediary state waits for active order to finish pending (if exist) and cancel it
    intermediary state: run() returns True when complete
    """

    name = TradeStates.BIN

    def run(
            self,
            trade_tracker: TradeTracker,
            **inputs
    ):
        # check if order exists
        if trade_tracker.active_order is None:
            return True

        # get order status
        sts = trade_tracker.active_order.status

        if sts in [OrderStatus.PENDING, OrderStatus.UPDATING, OrderStatus.REPLACING]:
            # still pending
            return None

        elif sts == OrderStatus.EXECUTABLE:
            # partial match, cancel() checks for EXECUTABLE state when this when called
            trade_tracker.active_order.cancel(trade_tracker.active_order.size_remaining)
            return True

        else:
            # order complete/failed, can exit
            return True


class TradeStateHedgeSelect(TradeStateBase):
    """
    proceed to hedge placement state, defined by `next_state`
    proceed to 'hedge_state' if found in `inputs` kwargs in run()
    """
    name = TradeStates.HEDGE_SELECT
    next_state = TradeStates.HEDGE_PLACE_TAKE

    def run(self, **inputs):
        return inputs.get('hedge_state', self.next_state)


class TradeStateHedgePlaceTake(TradeStateBase):
    """
    place an order to hedge active trade orders at the available price
    """

    name = TradeStates.HEDGE_PLACE_TAKE
    next_state = TradeStates.HEDGE_TAKE_MATCHING

    def __init__(self, min_hedge_price, name: TradeStates = None, next_state: TradeStates = None):
        super().__init__(name, next_state)
        self.min_hedge_price = min_hedge_price

    def get_hedge_price(
            self,
            open_ladder: List[Dict],
            close_ladder: List[Dict],
            close_side,
            trade_tracker: TradeTracker
    ):
        """
        take best available price
        e.g. if trade was opened as a back (the 'open_side') argument, then take lowest lay price available (the
        'close_side')
        """
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

        match_bet_sums = get_match_bet_sums(trade_tracker.active_trade)
        outstanding_profit = match_bet_sums.outstanding_profit()
        if abs(outstanding_profit) <= self.min_hedge_price:
            trade_tracker.log_update(
                f'win/loss diff £{outstanding_profit:.2f} doesnt exceed required hedge amount £'
                f'{self.min_hedge_price:.2f}',
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
            trade_tracker.log_update('one side of book is completely empty...', market_book.publish_time)
            return TradeStates.CLEANING

        green_price = self.get_hedge_price(open_ladder, close_ladder, close_side, trade_tracker)

        if not green_price:
            trade_tracker.log_update(
                f'invalid green price {green_price}',
                market_book.publish_time
            )
            return TradeStates.CLEANING

        green_size = abs(outstanding_profit) / green_price
        green_size = round(green_size, 2)

        trade_tracker.log_update(
            f'greening active order side {close_side} on {green_price} for £{green_size:.2f}',
            market_book.publish_time,
            display_odds=green_price,
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


class TradeStateHedgeTakeWait(TradeStateBase):
    """
    wait for hedge at available price to complete
    if price moves before complete, adjust price to match
    a known disadvantage of this is if the price drifts massively, it will not account for the drop in stake required
    """

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
            trade_tracker.log_update(
                f'error trying to hedge: "{order.status}, retrying...',
                market_book.publish_time
            )
            return TradeStates.HEDGE_PLACE_TAKE
        elif order.status == OrderStatus.EXECUTION_COMPLETE:
            return self.next_state
        elif order.status not in order_pending_states and order.status != OrderStatus.CANCELLING:
            # get ladder on close side for hedging
            available = select_ladder_side(
                market_book.runners[runner_index].ex,
                order.side
            )
            # get operator for comparing available price and current hedge price
            op = select_operator_side(
                order.side,
                invert=True
            )
            # if current price is not the same as order price then move
            if available and op(available[0]['price'], order.order_type.price):
                trade_tracker.log_update(
                    f'cancelling hedge at {order.order_type.price} for new price {available[0]["price"]}',
                    # f'moving hedge price from {order.order_type.price} to {available[0]["price"]}',
                    market_book.publish_time,
                    display_odds=available[0]['price'],
                )
                return [TradeStates.BIN, TradeStates.HEDGE_PLACE_TAKE]
                # replacing doesn't seem to work in back-test mode
                # order.replace(available[0]['price'])


# TODO - implement
class TradeStateClean(TradeStateBase):

    name = TradeStates.CLEANING

    def run(self, **kwargs):
        pass


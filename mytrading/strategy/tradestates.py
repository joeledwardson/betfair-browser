from enum import Enum
from typing import List, Union
from datetime import datetime, timedelta
from flumine.controls.clientcontrols import MaxTransactionCount

from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.ordertype import LimitOrder, OrderTypes
from flumine.order.trade import TradeStatus
from betfairlightweight.resources.bettingresources import RunnerBook

from ..process import MatchBetSums, get_order_profit, get_side_operator, get_side_ladder, side_invert, closest_tick, \
    LTICKS_DECODED
from ..exceptions import TradeStateException
from mytrading.strategy.messages import MessageTypes
from .runnerhandler import RunnerHandler
from myutils import mystatemachine as stm


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


class TradeStateTypes(Enum):
    """
    Enumeration of trade state keys used for names in state instances
    """

    BASE =                  'unimplemented'
    CREATE_TRADE =          'create trade'
    IDLE =                  'unplaced'
    OPEN_PLACING =          'placing opening trade'
    OPEN_MATCHING =         'waiting for opening trade to match'
    BIN =                   'bottling trade'
    HEDGE_SELECT =          'selecting type of hedge'
    HEDGE_TAKE_PLACE =      'place hedge trade at available price'
    HEDGE_TAKE_MATCHING =   'waiting for hedge to match at available price'
    HEDGE_QUEUE_PLACE =     'queue hedge trade'
    HEDGE_QUEUE_MATCHING =  'wait for queue hedge to finish'
    CLEANING =              'cleaning trade'
    PENDING =               'pending state'
    WAIT =                  'wait for a set number of milliseconds'


class TradeStateBase(stm.State):
    """
    base trading state for implementing sub-classes with run() defined
    """
    # override default state name and next state without the need for sub-class
    def __init__(self, name: Enum = None, next_state: Enum = None):
        if name:
            self.name = name
        if next_state:
            self.next_state = next_state

    # set this value to false where entering into state should not be printed to info log in trademachine
    print_change_message = True
    # use enumerations for name of state for other states to refer to
    name: TradeStateTypes = TradeStateTypes.BASE
    # easily overridable state to progress to when state action is complete
    next_state: TradeStateTypes = TradeStateTypes.BASE

    def enter(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        """
        initialise a state
        """
        pass

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
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


class TradeStateIntermediary(TradeStateBase):
    """
    Intermediary state
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'next_state' in kwargs:
            raise TradeStateException(f'next_state kwarg found in intermediary state')


class TradeStatePending(TradeStateIntermediary):
    """
    intermediary state for waiting for trade to process
    intermediary state: run() returns True when complete

    Specifying `all_trade_orders=True` means all orders within active trade are checked, rather than just the active
    order
    """
    name = TradeStateTypes.PENDING

    def __init__(self, all_trade_orders=False, delay_once=False, **kwargs):
        super().__init__(**kwargs)
        self.all_trade_orders = all_trade_orders
        self.delay_once = delay_once
        self.first_call = True

    def enter(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        self.first_call = True

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        """called to operate state - return None to remain in same state, or return string for new state"""
        # hold for 1 state
        if self.first_call:
            self.first_call = False
            if self.delay_once:
                return False

        # select either active order or all active trade orders
        trk = runner_handler.trade_tracker
        if not self.all_trade_orders:
            orders = [trk.active_order]
        else:
            orders = trk.active_trade.orders if trk.active_trade else []

        # loop orders
        for order in orders:
            # ignore, go to next order if doesn't exist
            if order is None:
                continue
            # if order in pending states then not done yet, don't exit state
            if order.status in order_pending_states:
                return False

        # exit state if all order(s) not pending
        return True


class TradeStateBin(TradeStateIntermediary):
    """
    intermediary state waits for active order to finish pending (if exist) and cancel it
    intermediary state: run() returns True when complete
    """
    name = TradeStateTypes.BIN

    def __init__(self, all_trade_orders=False, **kwargs):
        super().__init__(**kwargs)
        self.all_trade_orders = all_trade_orders

    def run(self, market: Market, runner_index: BaseStrategy, runner_handler: RunnerHandler):
        trk = runner_handler.trade_tracker
        # select either active order or all active trade orders
        if not self.all_trade_orders:
            orders = [trk.active_order]
        else:
            orders = [o for o in trk.active_trade.orders] if trk.active_trade else []
        done = True

        # loop orders
        for order in orders:
            # ignore, go to next order if doesn't exist
            if order is None:
                continue
            # if order in pending states then not done yet, don't exit state
            if order.status in order_pending_states:
                done = False

            elif order.status == OrderStatus.EXECUTABLE:
                # check if order has been called to be cancelled but has gone back to EXECUTABLE before finishing
                if len(order.status_log) >= 2 and order.status_log[-2] == OrderStatus.CANCELLING:
                    pass
                else:
                    # cancel order (flumine checks order is EXECUTABLE before cancelling or throws error)
                    market.cancel_order(order)
                done = False

        return done


class TradeStateWait(TradeStateIntermediary):
    """
    Intermediary state that waits for a designates number of milliseconds before continuing
    """
    name = TradeStateTypes.WAIT

    def __init__(self, wait_ms, **kwargs):
        super().__init__(**kwargs)
        self.wait_ms = wait_ms
        self.td = timedelta(milliseconds=wait_ms)
        self.start_time = datetime.now()

    def enter(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        self.start_time = market.market_book.publish_time

    def run(self, market: Market, runner_index: BaseStrategy, runner_handler: RunnerHandler):
        return (market.market_book.publish_time - self.start_time) >= self.td


# core states
class TradeStateCreateTrade(TradeStateBase):
    """
    Create trade instance and move to next state
    """
    name = TradeStateTypes.CREATE_TRADE
    next_state = TradeStateTypes.IDLE

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        runner_handler.trade_tracker.create_trade(
            handicap=market.market_book.runners[runner_index].handicap
        )
        return self.next_state


class TradeStateIdle(TradeStateBase):
    """
    idle state, waiting to open trade as specified by implementing in sub-classes trade_criteria() function
    Once trade_criteria() returns True, will move to next state
    """
    name = TradeStateTypes.IDLE
    next_state = TradeStateTypes.OPEN_PLACING

    # on entering IDLE state dont print update message
    print_change_message = False

    def __init__(self, trade_transactions_cutoff, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trade_transactions_cutoff = trade_transactions_cutoff

    # return true to move to next state opening trade, false to remain idle
    def trade_criteria(self, market: Market, runner_index: int, runner_handler: RunnerHandler) -> bool:
        raise NotImplementedError

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        max_order_count: MaxTransactionCount = market.flumine.client.trading_controls[0]
        if self.trade_transactions_cutoff and max_order_count.transaction_count >= self.trade_transactions_cutoff:
            return None

        if self.trade_criteria(market, runner_index, runner_handler):
            return self.next_state


class TradeStateOpenPlace(TradeStateBase):
    """
    place an opening trade
    """
    name = TradeStateTypes.OPEN_PLACING
    next_state = TradeStateTypes.OPEN_MATCHING

    def place_order(self, market: Market, runner_index: int, runner_handler: RunnerHandler) -> Union[None, BetfairOrder]:
        raise NotImplementedError

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        limit_order = self.place_order(market, runner_index, runner_handler)
        if not limit_order:
            return [TradeStateTypes.PENDING, self.next_state]
        else:
            runner_handler.trade_tracker.log_update(
                msg_type=MessageTypes.MSG_OPEN_PLACE,
                msg_attrs={
                    'side':  limit_order.side,
                    'price': limit_order.order_type.price,
                    'size': limit_order.order_type.size,
                },
                dt=market.market_book.publish_time,
                display_odds=limit_order.order_type.price,
                order=limit_order
            )
            runner_handler.trade_tracker.active_order = limit_order
            runner_handler.trade_tracker.open_side = limit_order.side
            return [TradeStateTypes.PENDING, self.next_state]


class TradeStateOpenMatching(TradeStateBase):
    """
    wait for open trade to match
    """
    name = TradeStateTypes.OPEN_MATCHING
    next_state = TradeStateTypes.HEDGE_SELECT

    def __init__(self, move_on_complete=True, *args, **kwargs):
        """
        Parameters
        ----------
        move_on_complete : specifies whether to move to next state once active order status becomes EXECUTION_COMPLETE
        """
        self.move_on_complete = move_on_complete
        super().__init__(*args, **kwargs)

    def open_order_processing(
            self, market: Market, runner_index: int, runner_handler: RunnerHandler
    ) -> Union[None, List[Enum]]:
        """return new state(s) if different action required, otherwise None"""
        raise NotImplementedError

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        new_states = self.open_order_processing(market, runner_index, runner_handler)
        if new_states:
            return new_states
        else:
            sts = runner_handler.trade_tracker.active_order.status
            if sts == OrderStatus.EXECUTION_COMPLETE and self.move_on_complete:
                return self.next_state
            elif sts in order_error_states:
                runner_handler.trade_tracker.log_update(
                    msg_type=MessageTypes.MSG_OPEN_ERROR,
                    msg_attrs={
                        'order_status': str(sts),
                    },
                    dt=market.market_book.publish_time
                )
                return self.next_state


class TradeStateHedgeSelect(TradeStateBase):
    """
    proceed to hedge placement state, defined by `next_state`
    """
    name = TradeStateTypes.HEDGE_SELECT
    next_state = TradeStateTypes.HEDGE_TAKE_PLACE

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        return self.next_state


class TradeStateHedgePlaceBase(TradeStateBase):
    """
    base class of placing a hedging order, but not defining how to get the price to place hedge at
    - checks if outstanding profit between win/loss meets minimum requirement to place hedge trade, if fail go to clean
    - check that ladder back/lay is available and that unimplemented method get_hedge_price() doesn't return 0 before
    - placing trade
    """
    def __init__(self, min_hedge_price, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_hedge_price = min_hedge_price

    def get_hedge_price(
            self, market: Market, runner_index: int, runner_handler: RunnerHandler, outstanding_profit: float
    ) -> float:
        raise NotImplementedError

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        # get outstanding profit on trade (dif between profit in win/loss case)
        match_bet_sums = MatchBetSums.get_match_bet_sums(runner_handler.trade_tracker.active_trade)
        outstanding_profit = match_bet_sums.outstanding_profit()

        # abort if below minimum required to hedge
        if abs(outstanding_profit) <= self.min_hedge_price:
            runner_handler.trade_tracker.log_update(
                msg_type=MessageTypes.MSG_HEDGE_NOT_MET,
                msg_attrs={
                    'outstanding_profit': outstanding_profit,
                    'min_hedge': self.min_hedge_price
                },
                dt=market.market_book.publish_time
            )
            return TradeStateTypes.CLEANING

        # check that ladders not empty
        runner = market.market_book.runners[runner_index]
        if not runner.ex.available_to_lay or not runner.ex.available_to_back:
            runner_handler.trade_tracker.log_update(
                msg_type=MessageTypes.MSG_BOOKS_EMPTY,
                dt=market.market_book.publish_time
            )
            # wait for ladder to populate
            return None

        if outstanding_profit > 0:
            # value is positive: trade is "underlayed", i.e. needs more lay money
            close_side = 'LAY'
            close_ladder = runner.ex.available_to_lay
        else:
            # value is negative: trade is "overlayed", i.e. needs more back moneyy
            close_side = 'BACK'
            close_ladder = runner.ex.available_to_back

        # get green price for hedging, round to 2dp
        green_price = self.get_hedge_price(market, runner_index, runner_handler, outstanding_profit)
        green_price = round(green_price, ndigits=2)

        # if function returns 0 or invalid then error
        if green_price <= 0 or green_price and green_price not in LTICKS_DECODED:
            runner_handler.trade_tracker.log_update(
                msg_type=MessageTypes.MSG_GREEN_INVALID,
                msg_attrs={
                    'green_price': green_price
                },
                dt=market.market_book.publish_time
            )
            # use best available
            green_price = close_ladder[0]['price']

        # compute size from outstanding profit and price, round to 2dp
        green_size = abs(outstanding_profit) / green_price
        green_size = round(green_size, 2)

        # TODO (temporary fix so that orders are processed)
        runner_handler.trade_tracker.active_trade._update_status(TradeStatus.PENDING)

        # TODO - handle order errors
        # place order
        green_order = runner_handler.trade_tracker.active_trade.create_order(
            side=close_side,
            order_type=LimitOrder(
                price=green_price,
                size=green_size
            )
        )

        market.place_order(green_order)
        runner_handler.trade_tracker.log_update(
            msg_type=MessageTypes.MSG_GREEN_PLACE,
            msg_attrs={
                'close_side': close_side,
                'green_price': green_price,
                'green_size': green_size,
                'order_id': str(green_order.id),
            },
            dt=market.market_book.publish_time,
            display_odds=green_price,
        )

        runner_handler.trade_tracker.active_order = green_order
        return [TradeStateTypes.PENDING, self.next_state]


class TradeStateHedgeWaitBase(TradeStateBase):
    """
    base class for waiting for hedge trade to match
    price_moved() provides unimplemented method to detect whether price has moved and need to move hedging price
    """

    def __init__(self, hedge_place_state, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hedge_place_state = hedge_place_state

    def price_moved(self, market: Market, runner_index: int, runner_handler: RunnerHandler) -> float:
        """
        determines whether a new hedge price is available and should be taken
        if new hedge price available, return its price otherwise 0
        """
        raise NotImplementedError

    def compare_price(self, new_price, current_price, order_side, runner: RunnerBook) -> bool:
        """
        Compare suggested new price for hedging order to current price of hedging order. Return True if current hedge
        order should be replaced with new price or False to leave as is
        """
        return new_price != current_price

    def run(self, market: Market, runner_index: int, runner_handler):

        order = runner_handler.trade_tracker.active_order

        # check if there has been an error with the order
        if order.status in order_error_states:
            runner_handler.trade_tracker.log_update(
                msg_type=MessageTypes.MSG_HEDGE_ERROR,
                msg_attrs={
                    'order_status': order.violation_msg,
                },
                dt=market.market_book.publish_time
            )

            # try to hedge again
            return TradeStateTypes.HEDGE_SELECT

        elif order.status == OrderStatus.EXECUTION_COMPLETE:

            # hedge done, move on
            return self.next_state

        elif order.status == OrderStatus.CANCELLING:

            # hedge cancelling, try again
            return TradeStateTypes.HEDGE_SELECT

        elif order.status == OrderStatus.EXECUTABLE:

            # hedge matching, get new price
            new_price = self.price_moved(market, runner_index, runner_handler)

            # non-zero value indicates price has moved
            runner = market.market_book.runners[runner_index]
            if new_price and self.compare_price(new_price, order.order_type.price, order.side, runner):

                runner_handler.trade_tracker.log_update(
                    msg_type=MessageTypes.MSG_HEDGE_REPLACE,
                    msg_attrs={
                        'old_price': order.order_type.price,
                        'new_price': new_price
                    },
                    dt=market.market_book.publish_time,
                    display_odds=new_price,
                )

                # bin active hedge and hedge again with new price
                return [
                    TradeStateTypes.BIN,
                    self.hedge_place_state
                ]
                # replacing doesn't seem to work in back-test mode
                # order.replace(available[0]['price'])

        else:
            # theoretically should never reach here - pending states covered, error states, EXECUTABLE and
            # EXECUTION_COMPLETE
            runner_handler.trade_tracker.log_update(
                msg_type=MessageTypes.MSG_HEDGE_UNKNOWN,
                msg_attrs={
                    'order_status': order.status.value
                },
                dt=market.market_book.publish_time,
            )
            return [
                TradeStateTypes.BIN,
                TradeStateTypes.HEDGE_SELECT
            ]


class TradeStateHedgePlaceTake(TradeStateHedgePlaceBase):
    """
    place an order to hedge active trade orders at the available price
    """

    name = TradeStateTypes.HEDGE_TAKE_PLACE
    next_state = TradeStateTypes.HEDGE_TAKE_MATCHING

    def get_hedge_price(
            self, market: Market, runner_index: int, runner_handler: RunnerHandler, outstanding_profit: float
    ) -> float:
        ex = market.market_book.runners[runner_index].ex
        if outstanding_profit > 0:
            return ex.available_to_lay[0]['price']
        else:
            return ex.available_to_back[0]['price']


class TradeStateHedgeWaitTake(TradeStateHedgeWaitBase):
    """
    sees if available price on ladder has moved since placement
    """

    name = TradeStateTypes.HEDGE_TAKE_MATCHING
    next_state = TradeStateTypes.CLEANING

    def price_moved(self, market: Market, runner_index: int, runner_handler: RunnerHandler) -> float:
        # check active order exists
        order = runner_handler.trade_tracker.active_order
        if not order:
            return 0

        # get ladder on close side for hedging
        available = get_side_ladder(
            market.market_book.runners[runner_index].ex,
            order.side
        )

        # get operator for comparing available price and current hedge price
        op = get_side_operator(
            order.side,
            invert=True
        )

        # get available price for hedging if not empty
        new_price = available[0]['price'] if available else 0

        # if current price is not the same as order price then move
        if new_price and op(new_price, order.order_type.price):
            return new_price
        else:
            return 0


class TradeStateHedgePlaceQueue(TradeStateHedgePlaceBase):
    """
    Queue a hedge order at best price available on opposite side of the book
    e.g. if hedging on back side, best back is 4.1 and best lay is 4.5 then queue back order at 4.5

    Can specify tick offset for queue, e.g. for 1 tick offset and the example above then would queue back order at 4.4
    """

    name = TradeStateTypes.HEDGE_QUEUE_PLACE
    next_state = TradeStateTypes.HEDGE_QUEUE_MATCHING

    def __init__(self, tick_offset=0, **kwargs):
        super().__init__(**kwargs)
        self.tick_offset = tick_offset

    def get_hedge_price(
            self, market: Market, runner_index: int, runner_handler: RunnerHandler, outstanding_profit: float
    ) -> float:
        runner = market.market_book.runners[runner_index]
        if outstanding_profit > 0:
            # value is positive: trade is "underlayed", i.e. needs more lay money
            close_side = 'LAY'
            open_ladder = runner.ex.available_to_back
        else:
            # value is negative: trade is "overlayed", i.e. needs more back moneyy
            close_side = 'BACK'
            open_ladder = runner.ex.available_to_lay

        price = open_ladder[0]['price']
        if not self.tick_offset:
            return price

        index = closest_tick(price, return_index=True)
        if close_side == 'BACK':
            index = max(index - self.tick_offset, 0)
        else:
            index = min(index + self.tick_offset, len(LTICKS_DECODED) - 1)

        return LTICKS_DECODED[index]


class TradeStateHedgeWaitQueue(TradeStateHedgeWaitBase):
    """
    Wait for queued hedge to match, if price moves for given period of time then chase
    """

    name = TradeStateTypes.HEDGE_QUEUE_MATCHING
    next_state = TradeStateTypes.CLEANING

    def __init__(self, hold_time_ms: int, tick_offset=0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hold_time_ms = hold_time_ms
        self.tick_offset = tick_offset
        self.reset_time: datetime = datetime.now()
        self.moving = False
        self.original_price = 0

    def enter(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        self.reset_time = market.market_book.publish_time
        self.moving = False
        self.original_price = 0

    def compare_price(self, new_price, current_price, order_side, runner: RunnerBook) -> bool:
        """
        when placing queue hedges, in live mode any orders that are offset from queue price on opposite side of the
        book will become best available price so could cause recursion

        e.g. best back is 2.3 and best lay is 2.6, if back order is queued 2 ticks away at 2.56 then the market will
        update that best lay is now 2.56 and this state would immediately replace the order with 2.54, so on and so
        forth..

        Thus, when queing updates and back order shortens or lay order drifts, only update price if the availble
        price is better than what we are offering.
        e.g. best back is 2.3 and best lay is 2.6, back order queued 2 ticks away at 2.56 - if best back then updated to
        2.54, then order would be updated to 2 ticks away at 2.50
        """
        if order_side == 'BACK':
            atl = runner.ex.available_to_lay
            if atl:
                best_lay = atl[0]['price']
                if best_lay < current_price:
                    return True
        elif order_side == 'LAY':
            atb = runner.ex.available_to_back
            if atb:
                best_back = atb[0]['price']
                if best_back > current_price:
                    return True
        return False

    def price_moved(self, market: Market, runner_index: int, runner_handler: RunnerHandler) -> float:

        market_book = market.market_book
        trade_tracker = runner_handler.trade_tracker

        # check active order exists
        order = trade_tracker.active_order
        if not order:
            return 0

        # get ladder on open side for hedging
        available = get_side_ladder(
            market_book.runners[runner_index].ex,
            side_invert(order.side)
        )

        # check not empty
        if not available:
            return 0

        # get available price
        new_price = available[0]['price']
        price_index = closest_tick(new_price, return_index=True)
        if order.side == 'BACK':
            price_index = max(price_index - self.tick_offset, 0)
            new_price = LTICKS_DECODED[price_index]
            proceed = new_price < order.order_type.price
        else:
            price_index = min(price_index + self.tick_offset, len(LTICKS_DECODED) - 1)
            new_price = LTICKS_DECODED[price_index]
            proceed = new_price > order.order_type.price

        if not self.moving:
            if proceed:
                self.moving = True
                self.reset_time = market_book.publish_time
                self.original_price = order.order_type.price
        else:
            if proceed:
                if (market_book.publish_time - self.reset_time) > timedelta(milliseconds=self.hold_time_ms):
                    return new_price
            else:
                self.moving = False

        # price not moved
        return 0


class TradeStateClean(TradeStateBase):

    name = TradeStateTypes.CLEANING

    def enter(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        market_book = market.market_book
        trade_tracker = runner_handler.trade_tracker
        if trade_tracker.active_trade:
            # filter to limit orders
            orders = [o for o in trade_tracker.active_trade.orders if o.order_type.ORDER_TYPE == OrderTypes.LIMIT]

            win_profit = sum(
                get_order_profit(
                    'WINNER',
                    o.side,
                    o.average_price_matched,
                    o.size_matched)
                for o in orders)

            loss_profit = sum(
                get_order_profit(
                    'LOSER',
                    o.side,
                    o.average_price_matched,
                    o.size_matched)
                for o in orders)

            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_TRADE_COMPLETE,
                msg_attrs={
                    'win_profit': win_profit,
                    'loss_profit': loss_profit
                },
                dt=market_book.publish_time
            )

    def run(self, market: Market, runner_index: int, runner_handler: RunnerHandler):
        pass


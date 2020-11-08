from enum import Enum
from typing import List, Dict, Union

from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.ordertype import LimitOrder, OrderTypes
from flumine.order.trade import Trade

from ..process.matchbet import get_match_bet_sums
from ..process.profit import order_profit
from ..process.side import select_ladder_side, select_operator_side, invert_side
from ..tradetracker.tradetracker import TradeTracker
from ..tradetracker.messages import MessageTypes
from myutils import statemachine as stm


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


class TradeStateTypes(Enum):
    """
    Enumeration of trade state keys used for names in state instances
    """

    BASE =              'unimplemented'
    CREATE_TRADE =      'create trade'
    IDLE =              'unplaced'
    OPEN_PLACING =      'placing opening trade'
    OPEN_MATCHING =     'waiting for opening trade to match'
    BIN =               'bottling trade'
    HEDGE_SELECT =      'selecting type of hedge'
    HEDGE_PLACE_TAKE =  'place hedge trade at available price'
    HEDGE_TAKE_MATCHING='waiting for hedge to match at available price'
    CLEANING =          'cleaning trade'
    PENDING =           'pending state'


class TradeStateBase(stm.State):
    """
    base trading state for implementing sub-classes with run() defined
    """

    # override default state name and next state without the need for sub-class
    def __init__(self, name: TradeStateTypes = None, next_state: TradeStateTypes = None):
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

    def enter(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        """
        initialise a state
        """
        pass

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

    name = TradeStateTypes.PENDING

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_call = True

    def enter(self, **inputs):
        self.first_call = True

    # called to operate state - return None to remain in same state, or return string for new state
    def run(self, trade_tracker: TradeTracker, **inputs):

        # check order exists
        if trade_tracker.active_order is None:
            return True

        if trade_tracker.active_order.status not in order_pending_states:
            # wait 1 cycle before exiting state
            if not self.first_call:
                return True

        self.first_call = False


class TradeStateCreateTrade(TradeStateBase):
    """
    Create trade instance and move to next state
    """
    name = TradeStateTypes.CREATE_TRADE
    next_state = TradeStateTypes.IDLE

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
    name = TradeStateTypes.IDLE
    next_state = TradeStateTypes.OPEN_PLACING

    # on entering IDLE state dont print update message
    print_change_message = False

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
        if self.trade_criteria(
                market_book=market_book,
                market=market,
                runner_index=runner_index,
                trade_tracker=trade_tracker,
                strategy=strategy,
                **inputs):
            return self.next_state


class TradeStateOpenPlace(TradeStateBase):
    """
    place an opening trade
    """
    name = TradeStateTypes.OPEN_PLACING
    next_state = TradeStateTypes.OPEN_MATCHING

    def place_order(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs) -> Union[None, BetfairOrder]:
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
        limit_order = self.place_order(market_book, market, runner_index, trade_tracker, strategy, **inputs)
        if not limit_order:
            return [TradeStateTypes.PENDING, self.next_state]
        else:
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_OPEN_PLACE,
                msg_attrs={
                    'side':  limit_order.side,
                    'price': limit_order.order_type.price,
                    'size': limit_order.order_type.size,
                },
                dt=market_book.publish_time,
                display_odds=limit_order.order_type.price,
                order=limit_order
            )
            trade_tracker.active_order = limit_order
            trade_tracker.open_side = limit_order.side
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

    # return new state(s) if different action required, otherwise None
    def open_order_processing(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ) -> Union[None, List[Enum]]:
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
        new_states = self.open_order_processing(market_book, market, runner_index, trade_tracker, strategy, **inputs)
        if new_states:
            return new_states
        else:
            sts = trade_tracker.active_order.status

            if sts == OrderStatus.EXECUTION_COMPLETE and self.move_on_complete:
                return self.next_state

            elif sts in order_error_states:
                trade_tracker.log_update(
                    msg_type=MessageTypes.MSG_OPEN_ERROR,
                    msg_attrs={
                        'order_status': str(sts),
                    },
                    dt=market_book.publish_time
                )
                return self.next_state


class TradeStateBin(TradeStateBase):

    """
    intermediary state waits for active order to finish pending (if exist) and cancel it
    intermediary state: run() returns True when complete
    """

    name = TradeStateTypes.BIN

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
            # cancel active order
            trade_tracker.active_order.cancel(trade_tracker.active_order.size_remaining)
            # can immediately exit state as hopefully user has put pending state next to wait 1 cycle
            return True

        else:
            # order complete/failed, can exit
            return True


class TradeStateHedgeSelect(TradeStateBase):
    """
    proceed to hedge placement state, defined by `next_state`
    proceed to 'hedge_state' if found in `inputs` kwargs in run()
    """
    name = TradeStateTypes.HEDGE_SELECT
    next_state = TradeStateTypes.HEDGE_PLACE_TAKE

    def run(self, **inputs):
        return inputs.get('hedge_state', self.next_state)


class TradeStateHedgePlaceBase(TradeStateBase):
    """
    base class of placing a hedging order, but not defining how to get the price to place hedge at
    - checks if outstanding profit between win/loss meets minimum requirement to place hedge trade, if fail go to clean
    - check that ladder back/lay is available and that unimplemented method get_hedge_price() doesn't return 0 before
    - placing trade
    """

    name = TradeStateTypes.HEDGE_PLACE_TAKE
    next_state = TradeStateTypes.HEDGE_TAKE_MATCHING

    def __init__(self, min_hedge_price, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_hedge_price = min_hedge_price

    def get_hedge_price(
            self,
            open_ladder: List[Dict],
            close_ladder: List[Dict],
            close_side,
            trade_tracker: TradeTracker,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            strategy: BaseStrategy,
            **inputs
    ) -> float:
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

        # get oustanding profit on trade (dif between profit in win/loss case)
        match_bet_sums = get_match_bet_sums(trade_tracker.active_trade)
        outstanding_profit = match_bet_sums.outstanding_profit()

        # abort if below minimum required to hedge
        if abs(outstanding_profit) <= self.min_hedge_price:
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_HEDGE_NOT_MET,
                msg_attrs={
                    'outstanding_profit': outstanding_profit,
                    'min_hedge': self.min_hedge_price
                },
                dt=market_book.publish_time
            )
            return TradeStateTypes.CLEANING

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

        # check that ladders not empty
        if not close_ladder:
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_BOOKS_EMPTY,
                dt=market_book.publish_time
            )

            # wait for ladder to populate
            return None

        # get green price for hedging
        green_price = self.get_hedge_price(
            open_ladder,
            close_ladder,
            close_side,
            trade_tracker,
            market_book,
            market,
            runner_index,
            strategy,
            **inputs
        )

        # convert price to 2dp
        green_price = round(green_price, ndigits=2)

        # if function returns 0 then error
        if not green_price:
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_GREEN_INVALID,
                msg_attrs={
                    'green_price': green_price
                },
                dt=market_book.publish_time
            )

            # try repeat
            return None

        # compute size from outstanding profit and price, round to 2dp
        green_size = abs(outstanding_profit) / green_price
        green_size = round(green_size, 2)

        # place order
        trade_tracker.log_update(
            msg_type=MessageTypes.MSG_GREEN_PLACE,
            msg_attrs={
                'close_side': close_side,
                'green_price': green_price,
                'green_size': green_size
            },
            dt=market_book.publish_time,
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
        return [TradeStateTypes.PENDING, self.next_state]


class TradeStateHedgePlaceTake(TradeStateHedgePlaceBase):
    """
    place an order to hedge active trade orders at the available price
    """

    def get_hedge_price(
            self,
            open_ladder: List[Dict],
            close_ladder: List[Dict],
            close_side,
            trade_tracker: TradeTracker,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            strategy: BaseStrategy,
            **inputs
    ):
        """
        take best available price
        e.g. if trade was opened as a back (the 'open_side') argument, then take lowest lay price available (the
        'close_side')
        """
        return close_ladder[0]['price'] if close_ladder else 0


class TradeStateHedgeWaitBase(TradeStateBase):
    """
    base class for waiting for hedge trade to match
    price_moved() provides unimplemented method to detect whether price has moved and need to move hedging price
    """

    name = TradeStateTypes.HEDGE_TAKE_MATCHING
    next_state = TradeStateTypes.CLEANING

    def price_moved(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ) -> float:
        """
        determines whether a new hedge price is available and should be taken
        if new hedge price available, return its price otherwise 0
        """
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

        order = trade_tracker.active_order

        # check if there has been an error with the order
        if order.status in order_error_states:
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_HEDGE_ERROR,
                msg_attrs={
                    'order_status': order.status.value,
                },
                dt=market_book.publish_time
            )

            # try to hedge again
            return TradeStateTypes.HEDGE_PLACE_TAKE

        elif order.status == OrderStatus.EXECUTION_COMPLETE:

            # hedge done, move on
            return self.next_state

        elif order.status == OrderStatus.CANCELLING:

            # hedge cancelling, try again
            return TradeStateTypes.HEDGE_PLACE_TAKE

        elif order.status == OrderStatus.EXECUTABLE:

            # hedge matching, get new price
            new_price = self.price_moved(
                market_book,
                market,
                runner_index,
                trade_tracker,
                strategy,
                **inputs
            )

            # non-zero value indicates price has moved
            if new_price:

                trade_tracker.log_update(
                    msg_type=MessageTypes.MSG_HEDGE_REPLACE,
                    msg_attrs={
                        'old_price': order.order_type.price,
                        'new_price': new_price
                    },
                    dt=market_book.publish_time,
                    display_odds=new_price,
                )

                # bin active hedge and hedge again with new price
                return [
                    TradeStateTypes.BIN,
                    TradeStateTypes.PENDING,
                    TradeStateTypes.HEDGE_PLACE_TAKE
                ]
                # replacing doesn't seem to work in back-test mode
                # order.replace(available[0]['price'])

        else:
            # theoretically should never reach here - pending states covered, error states, EXECUTABLE and
            # EXECUTION_COMPLETE
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_HEDGE_UNKNOWN,
                msg_attrs={
                    'order_status': order.status.value
                },
                dt=market_book.publish_time,
            )
            return [
                TradeStateTypes.BIN,
                TradeStateTypes.PENDING,
                TradeStateTypes.HEDGE_PLACE_TAKE
            ]


class TradeStateHedgeWaitTake(TradeStateHedgeWaitBase):
    """
    sees if available price on ladder has moved since placement
    """

    def price_moved(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ) -> float:

        # check active order exists
        order = trade_tracker.active_order
        if not order:
            return 0

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

        # get available price for hedging if not empty
        new_price = available[0]['price'] if available else 0

        # if current price is not the same as order price then move
        if new_price and op(new_price, order.order_type.price):
            return new_price
        else:
            return 0


class TradeStateClean(TradeStateBase):

    name = TradeStateTypes.CLEANING

    def enter(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):

        if trade_tracker.active_trade:

            # filter to limit orders
            orders = [o for o in trade_tracker.active_trade.orders if o.order_type.ORDER_TYPE == OrderTypes.LIMIT]

            win_profit = sum(
                order_profit(
                    'WINNER',
                    o.side,
                    o.average_price_matched,
                    o.size_matched)
                for o in orders)

            loss_profit = sum(
                order_profit(
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

    def run(self, **kwargs):
        pass


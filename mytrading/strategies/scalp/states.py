import logging
from datetime import datetime
from enum import Enum
from typing import List, Dict

from betfairlightweight.resources import MarketBook
from betfairlightweight.resources.bettingresources import RunnerBook
from flumine.markets.market import Market
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.ordertype import LimitOrder
from flumine import BaseStrategy

from .messages import WallMessageTypes
from mytrading.trademachine import tradestates
from mytrading.trademachine.tradestates import TradeStateTypes
from mytrading.process.ladder import runner_spread, BfLadderPoint
from mytrading.process.prices import best_price
from mytrading.process.ticks.ticks import TICKS, LTICKS_DECODED, LTICKS
from .walltradetracker import WallTradeTracker
from mytrading.strategy.side import select_ladder_side, invert_side, select_operator_side
from myutils import generic
from myutils.generic import i_prev, i_next


class WallTradeStateTypes(Enum):
    """
    additional wall trade state keys, used in conjunction with `bf_trademachine.TradeStates`
    """
    WALL_HEDGE_PLACE = 'wall hedge place'
    WALL_HEDGE_MATCHING = 'wall hedge trading matching'


def validate_wall(
        publish_time: datetime,
        runner_book: RunnerBook,
        trade_tracker: WallTradeTracker,
        wall_ticks,
        wall_validation,
) -> bool:
    """
    validate inputs against current wall information stored in 'trade_tracker'
    wall data is expected to be contained in  'wall_point' in 'inputs' as a BfLadderPoint instance
    - checks if required proportion of amount available at original wall price in 'trade_tracker' is there
    """

    # check wall exists in trade tracker
    if not trade_tracker.wall:
        trade_tracker.log_update(
            msg_type=WallMessageTypes.NO_WALL,
            dt=publish_time,
            level=logging.WARNING
        )

    # get ladder on wall side of book
    available = select_ladder_side(runner_book.ex, trade_tracker.wall.side)

    # limit tick range, if price drifts to much then bet will be cancelled if not matched
    available = available[:wall_ticks]

    # get original wall pricesize at point of placing trade
    wall_price_size = generic.get_object(available, lambda x: x['price'] == trade_tracker.wall.price)

    # if no money at original wall pricesize (or out of wall ticks range) then abort
    if not wall_price_size:
        trade_tracker.log_update(
            msg_type=WallMessageTypes.NO_WALL_PRICE,
            msg_attrs={
                'wall_price': trade_tracker.wall.price
            },
            dt=publish_time,
            display_odds=trade_tracker.wall.price,
        )
        return False

    # if size of bet at wall price has decreased by more than allowed amount for validation then abort
    if wall_price_size['size'] < wall_validation * trade_tracker.wall.size:
        trade_tracker.log_update(
            msg_type=WallMessageTypes.WALL_SIZE_FAIL,
            msg_attrs={
                'wall_price': trade_tracker.wall.price,
                'wall_size': wall_price_size["size"],
                'wall_validation': wall_validation,
                'old_wall_size': trade_tracker.wall.size
            },
            dt=publish_time,
            display_odds=trade_tracker.wall.price
        )
        return False

    return True


def get_wall_adjacent(
        wall_side,
        wall_tick_index
) -> float:
    """
    compute the new price of wall trade and store in `trade_tracker`, return new price
    - `wall_side` is the ladder side which wall is located (e.g. 'BACK' is available to back)
    - `wall_tick` is the index of the wall price in the array of prices (short to long)

    e.g. if `wall_side` is 'BACK' and `wall_tick` is 150 (price of 3.0) then a price of 3.02 (index 151) is returned
    """

    # get index of tick from wall price
    new_tick_index = wall_tick_index

    if wall_side == 'LAY':

        # wall is on available to lay side (i.e. back), want to back one tick lower
        new_tick_index = i_prev(new_tick_index)

    else:

        # wall is on available to back side (i.e. lay), want to lay one tick higher
        new_tick_index = i_next(new_tick_index, len(TICKS))

    # get price from tick index
    return LTICKS_DECODED[new_tick_index]


class WallTradeStateIdle(tradestates.TradeStateIdle):
    """
    Idle state implements `trade_criteria()` function, to return True (indicating move to open trade place state)
    once a valid wall is detected on inputs
    """

    def __init__(self, max_tick_spread, *args, **kwargs):
        self.max_tick_spread = max_tick_spread
        super().__init__(*args, **kwargs)

    # return true to move to next state opening trade, false to remain idle
    def trade_criteria(
            self,
            market_book: MarketBook,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            **inputs) -> bool:

        if inputs.get('wall_point') is not None:
            spread = runner_spread(market_book.runners[runner_index].ex)
            if spread <= self.max_tick_spread:
                trade_tracker.log_update(
                    msg_type=WallMessageTypes.WALL_DETECT,
                    msg_attrs={
                        'wall_point': inputs['wall_point'].__dict__,
                        'best_atb': best_price(market_book.runners[runner_index].ex.available_to_back),
                        'best_atl': best_price(market_book.runners[runner_index].ex.available_to_lay),
                        'spread_ticks': spread,
                    },
                    dt=market_book.publish_time,
                    display_odds=inputs['wall_point'].price,
                )
                return True


class WallTradeStateOpenPlace(tradestates.TradeStateOpenPlace):
    """
    State to place an opening trade, implementing `place_trade()` function - places a trade on tick above/below wall
    price sent via kwarg inputs
    """

    def __init__(self, stake_size, *args, **kwargs):
        self.stake_size = stake_size
        super().__init__(*args, **kwargs)

    def place_order(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: BaseStrategy,
            **inputs) -> BetfairOrder:

        # check if wall inputs are in extra kwargs
        if inputs.get('wall_point') is None:
            trade_tracker.log_update(
                msg_type=WallMessageTypes.WALL_VARIABLE_INVALID,
                dt=market_book.publish_time,
                level=logging.WARNING,
            )
            return None

        # store current wall inputs in trade tracker for future reference
        wall: BfLadderPoint = inputs['wall_point']
        trade_tracker.wall = wall
        price = get_wall_adjacent(wall.side, wall.tick_index)

        # wall side is given as available, so if £150 available to back at 2.5 we want to lay at 2.51
        side = invert_side(wall.side)

        # create and place order
        order = trade_tracker.active_trade.create_order(
            side=side,
            order_type=LimitOrder(
                price=price,
                size=self.stake_size
            ))
        strategy.place_order(market, order)

        return order


class WallTradeStateOpenMatching(tradestates.TradeStateOpenMatching):
    """
    Wait for open trade to match, implements `open_trade_processing()` to return state if state change required
    aborts if wall does not meet validation criteria from when it was detected at point of placing opening trade
    """

    def __init__(self, wall_ticks, wall_validation, *args, **kwargs):
        self.wall_ticks = wall_ticks
        self.wall_validation = wall_validation
        super().__init__(*args, **kwargs)

    # return new state(s) if different action required, otherwise None
    def open_order_processing(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):

        runner_book = market_book.runners[runner_index]

        # validate wall price is there
        if not validate_wall(
            publish_time=market_book.publish_time,
            runner_book=runner_book,
            trade_tracker=trade_tracker,
            wall_ticks=self.wall_ticks,
            wall_validation=self.wall_validation
        ):
            return [
                TradeStateTypes.BIN,
                TradeStateTypes.PENDING,
                TradeStateTypes.HEDGE_PLACE_TAKE
            ]

        # get > or < comparator for BACK/LAY side selection
        op = select_operator_side(trade_tracker.open_side)

        wall: BfLadderPoint = inputs['wall_point']

        if not wall:
            return

        # verify better wall price available
        if not op(wall.price, trade_tracker.wall.price):
            return

        # make sure order is executable before replacing (required)
        if trade_tracker.active_order.status != OrderStatus.EXECUTABLE:
            return

        # compute new adjacent better price
        new_price = get_wall_adjacent(wall.side, wall.tick_index)

        # replace order with better price
        trade_tracker.active_order.replace(new_price)

        # replace wall parameters
        trade_tracker.wall = wall

        trade_tracker.log_update(
            msg_type=WallMessageTypes.REPLACE_WALL_ORDER,
            msg_attrs={
                'price': trade_tracker.active_order.order_type.price,
                'new_price': new_price
            },
            dt=market_book.publish_time,
            display_odds=new_price
        )

        # wait for pending to complete then return to this state
        return [
            TradeStateTypes.PENDING,
            TradeStateTypes.OPEN_MATCHING
        ]


class WallTradeStateHedgeSelect(tradestates.TradeStateHedgeSelect):
    """
    select wall hedge trade placement state
    """
    next_state = WallTradeStateTypes.WALL_HEDGE_PLACE


class WallTradeStateHedgeOffset(tradestates.TradeStateHedgePlaceTake):
    """
    place hedge at number of ticks away from open price
    """
    name = WallTradeStateTypes.WALL_HEDGE_PLACE
    next_state = WallTradeStateTypes.WALL_HEDGE_MATCHING

    def __init__(
            self,
            tick_target,
            min_hedge_price,
            name: WallTradeStateTypes = None,
            next_state: WallTradeStateTypes = None,
    ):
        super().__init__(min_hedge_price, name, next_state)
        self.tick_target = tick_target

    def get_hedge_price(
            self,
            open_ladder: List[Dict],
            close_ladder: List[Dict],
            close_side,
            trade_tracker: WallTradeTracker
    ):

        wall_price_index = trade_tracker.wall.tick_index

        if close_side == 'BACK':

            # closing trade on back side so want biggest odds as possible
            wall_price_index = i_next(wall_price_index, len(LTICKS), increment=self.tick_target)

        else:

            # closing trade on lay side of the book so want smallest odds as possible
            wall_price_index = i_prev(wall_price_index, increment=self.tick_target)

        return LTICKS_DECODED[wall_price_index]


class WallTradeStateHedgeWait(tradestates.TradeStateBase):
    """
    wait for hedge to complete, if wall disappears then take available price
    """

    name = WallTradeStateTypes.WALL_HEDGE_MATCHING
    next_state = TradeStateTypes.CLEANING

    def __init__(self, wall_ticks, wall_validation, *args, **kwargs):
        self.wall_ticks = wall_ticks
        self.wall_validation = wall_validation
        super().__init__(*args, **kwargs)

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        order = trade_tracker.active_order

        if order.status == OrderStatus.EXECUTION_COMPLETE:
            # hedge complete
            return self.next_state

        if not validate_wall(
                market_book.publish_time,
                market_book.runners[runner_index],
                trade_tracker,
                self.wall_ticks,
                self.wall_validation) or order.status in tradestates.order_error_states:
            trade_tracker.log_update(
                msg_type=WallMessageTypes.WALL_TAKE_HEDGE,
                dt=market_book.publish_time,
            )
            # if wall has gone or error then abandon position and take whatever is available to hedge
            return [
                TradeStateTypes.BIN,
                TradeStateTypes.PENDING,
                TradeStateTypes.HEDGE_PLACE_TAKE
            ]
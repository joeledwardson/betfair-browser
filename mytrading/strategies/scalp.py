from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook

import mytrading.trademachine.tradestates
from mytrading.trademachine import trademachine as bftm
from mytrading.strategy.featurestrategy import MyFeatureStrategy
from mytrading.process.ladder import BfLadderPoint, get_ladder_point
from mytrading.tradetracker.tradetracker import TradeTracker
from mytrading.process.ticks.ticks import LTICKS_DECODED, LTICKS, TICKS
from mytrading.process.prices import best_price
from mytrading.process.ladder import runner_spread
from mytrading.strategy.side import select_ladder_side, select_operator_side, invert_side
from myutils.generic import i_prev, i_next
from myutils import generic


import logging
from typing import List, Dict
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


@dataclass
class WallTradeTracker(TradeTracker):
    wall: BfLadderPoint = field(default=None)


class WallTradeStates(Enum):
    """
    additional wall trade state keys, used in conjunction with `bf_trademachine.TradeStates`
    """
    WALL_HEDGE_PLACE = 'wall hedge place'
    WALL_HEDGE_MATCHING = 'wall hedge trading matching'


class MyScalpStrategy(MyFeatureStrategy):
    """
    detect "wall" of money at single price on one side of book that is significantly greater than money on other side of
    book
    place trades one tick ahead of "wall" and try to hedge up a few ticks away for a profit
    if wall disappears then abandon and take available price for greening
    """

    def __init__(self, *args, **kwargs):
        super().__init__('scalp', *args, **kwargs)

    StrategyTradeTracker = WallTradeTracker

    # minimum size of 'wall' stake
    wall_minimum_size = 100

    # minimum ratio of wall bet size above others
    wall_minimum_scale = 2

    # tick range when checking for wall stake
    wall_ticks = 5

    # stake size £
    stake_size = 5

    # percentage of wall size at point of placing trade for validation
    wall_validation = 0.9

    # tick target for greening away from wall
    tick_target = 3

    # minimum difference in profit/loss between selection win/loss where hedge trade is placed
    min_hedge_price = 0.5

    # maximum spread in ticks between back and lay
    max_tick_spread = 10

    def get_wall(self, runner_book: RunnerBook) -> BfLadderPoint:
        """
        get wall as a `BfLadderPoint`, return None if not found
        tries both 'BACK' and 'LAY' sides of the book searching for a wall using `self.get_wall_price_size`
        """

        for side in ['BACK', 'LAY']:
            wall_info = self.get_wall_price_size(
                runner_book=runner_book,
                side=side
            )
            if wall_info:
                wall_point = get_ladder_point(wall_info['price'], wall_info['size'], side)
                if wall_point:
                    return wall_point

        return None

    def get_wall_price_size(self, runner_book: RunnerBook, side):
        """
        get a dictionary containing 'price' and 'size' of wall on `side` of the book, return None on not found
        wall must be above required minimum size and above a certain scale of values on the opposing side of the book

        e.g. if `side` is 'BACK', `runner_book.ex.available_to_back` has £120 as 3.0 and lay side max money is: £50
        at 2.9, then {'price': 3.0, 'size': 120} is returned as:
        - £120 is greater than the required minimum of £100 in `self.wall_minimum_size`
        - £120 is more than 2x (from `self.wall_minimum_scale`) greater than all values on lay side
        """

        # get back and lay ladders, filtered to specified number of ticks
        atl = runner_book.ex.available_to_lay[:self.wall_ticks]
        atb = runner_book.ex.available_to_back[:self.wall_ticks]

        # ignore if empty
        if not atl or not atb:
            return None

        # pick the chosen side and 'opposing' side of books for comparison
        if side == 'BACK':
            chosen_book = atb
            oppose_book = atl
        else:
            chosen_book = atl
            oppose_book = atb

        # get the size of max bet and its index within array
        max_chosen_value, max_chosen_index = max((x['size'], i) for i, x in enumerate(chosen_book))
        # max_oppose_value, max_oppose_index = max((x['size'], i) for i, x in enumerate(oppose_book))

        # comparing to other values in the chosen book, and all values on opposide side
        compare_values = [x['size'] for i, x in enumerate(chosen_book) if i != max_chosen_index]
        compare_values += [x['size'] for x in oppose_book]

        # check the size is sufficient
        if max_chosen_value < self.wall_minimum_size:
            return None

        # check that value is sufficiently larger than other values
        if not all([max_chosen_value >= (self.wall_minimum_scale * s) for s in compare_values]):
            return None

        return chosen_book[max_chosen_index].copy()

    def create_state_machine(
            self,
            runner: RunnerBook,
            market: Market,
            market_book: MarketBook
    ) -> bftm.RunnerStateMachine:
        """
        get trading state machine for selected runner
        """

        return bftm.RunnerStateMachine(
            states={
                state.name: state
                for state in [
                    mytrading.trademachine.tradestates.TradeStateCreateTrade(),
                    WallTradeStateIdle(),
                    WallTradeStateOpenPlace(),
                    WallTradeStateOpenMatching(),
                    mytrading.trademachine.tradestates.TradeStateBin(),
                    mytrading.trademachine.tradestates.TradeStatePending(),
                    WallTradeStateHedgeSelect(),
                    WallTradeStateHedgeOffset(
                        tick_target=self.tick_target,
                        min_hedge_price=self.min_hedge_price
                    ),
                    WallTradeStateHedgeWait(),
                    mytrading.trademachine.tradestates.TradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price
                    ),
                    mytrading.trademachine.tradestates.TradeStateHedgeTakeWait(),
                    mytrading.trademachine.tradestates.TradeStateClean()
                ]
            },
            initial_state=mytrading.trademachine.tradestates.TradeStateCreateTrade.name,
            selection_id=runner.selection_id,
        )

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:

        # update feature data (calls market_initialisation() if new market)
        self.strategy_process_market_book(market, market_book)

        # loop runners
        for runner_index, runner in enumerate(market_book.runners):

            trade_tracker = self.trade_trackers[market.market_id][runner.selection_id]
            state_machine = self.state_machines[market.market_id][runner.selection_id]
            if self.process_trade_machine(runner, state_machine, trade_tracker):

                # get wall point for runner
                wall_point = self.get_wall(runner)

                state_machine.run(
                    market_book=market_book,
                    market=market,
                    runner_index=runner_index,
                    trade_tracker=trade_tracker,
                    strategy=self,
                    wall_point=wall_point
                )

            # update order tracker
            trade_tracker.update_order_tracker(market_book.publish_time)


def validate_wall(
        publish_time: datetime,
        runner_book: RunnerBook,
        trade_tracker: WallTradeTracker,
        strategy: MyScalpStrategy,
        **inputs
) -> bool:
    """
    validate inputs against current wall information stored in 'trade_tracker'
    wall data is expected to be contained in  'wall_point' in 'inputs' as a BfLadderPoint instance
    - checks if required proportion of amount available at original wall price in 'trade_tracker' is there
    """

    # check if wall still exists
    # if inputs.get('wall_point') is None:
    #     trade_tracker.log(
    #         f'wall validation failed: wall variables not detected/invalid: "{inputs.get("wall_point")}"',
    #         publish_time
    #     )
    #     return False

    # check wall exists in trade tracker
    if not trade_tracker.wall:
        trade_tracker.log_update(
            f'wall validation failed: no wall instance found in trade_tracker',
            publish_time,
            level=logging.WARNING
        )

    # check wall is on the right side
    # wall: BfLadderPoint = inputs['wall_point']
    # if wall.side != trade_tracker.wall.side:
    #     trade_tracker.log(
    #         f'wall validation failed:  wall side "{wall.side}" is not the same as original wall side '
    #         f'"{trade_tracker.wall.side}"',
    #         publish_time
    #     )
    #     return False

    # get ladder on wall side of book
    available = select_ladder_side(runner_book.ex, trade_tracker.wall.side)

    # limit tick range, if price drifts to much then bet will be cancelled if not matched
    available = available[:strategy.wall_ticks]

    # get original wall pricesize at point of placing trade
    wall_price_size = generic.get_object(available, lambda x: x['price'] == trade_tracker.wall.price)

    # if no money at original wall pricesize (or out of wall ticks range) then abort
    if not wall_price_size:
        trade_tracker.log_update(
            f'wall validation failed: no price info detected at wall price {trade_tracker.wall.price}',
            publish_time,
            display_odds=trade_tracker.wall.price,
        )
        return False

    # if size of bet at wall price has decreased by more than allowed amount for validation then abort
    if wall_price_size['size'] < strategy.wall_validation * trade_tracker.wall.size:
        trade_tracker.log_update(
            'wall validation failed:  current amount at wall price {0} of £{1:.2f} is less than validation multiplier '
            '{2} of original size £{3:.2f}'.format(
                trade_tracker.wall.price,
                wall_price_size["size"],
                strategy.wall_validation,
                trade_tracker.wall.size
            ),
            publish_time,
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


class WallTradeStateIdle(mytrading.trademachine.tradestates.TradeStateIdle):
    """
    Idle state implements `trade_criteria()` function, to return True (indicating move to open trade place state)
    once a valid wall is detected on inputs
    """

    # return true to move to next state opening trade, false to remain idle
    def trade_criteria(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: MyScalpStrategy,
            **inputs) -> bool:

        if inputs.get('wall_point') is not None:
            spread = runner_spread(market_book.runners[runner_index].ex)
            if spread <= strategy.max_tick_spread:
                trade_tracker.log_update(
                    'detected wall {0}, best back {1}, best lay {2}, spread ticks {3}'.format(
                        inputs["wall_point"],
                        best_price(market_book.runners[runner_index].ex.available_to_back),
                        best_price(market_book.runners[runner_index].ex.available_to_lay),
                        spread
                    ),
                    market_book.publish_time,
                    display_odds=inputs['wall_point'].price,
                )
                return True


class WallTradeStateOpenPlace(mytrading.trademachine.tradestates.TradeStateOpenPlace):
    """
    State to place an opening trade, implementing `place_trade()` function - places a trade on tick above/below wall
    price sent via kwarg inputs
    """

    def place_order(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: MyScalpStrategy,
            **inputs) -> BetfairOrder:

        # check if wall inputs are in extra kwargs
        if inputs.get('wall_point') is None:
            trade_tracker.log_update(
                f'wall variables detected not valid: {inputs.get("wall_point")}',
                market_book.publish_time,
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
                size=strategy.stake_size
            ))
        strategy.place_order(market, order)
        trade_tracker.log_update(
            f'placing open order at {price} for £{strategy.stake_size:.2f} on {side} side',
            market_book.publish_time,
            display_odds=price,
            order=order
        )
        return order


class WallTradeStateOpenMatching(mytrading.trademachine.tradestates.TradeStateOpenMatching):
    """
    Wait for open trade to match, implements `open_trade_processing()` to return state if state change required
    aborts if wall does not meet validation criteria from when it was detected at point of placing opening trade
    """

    # return new state(s) if different action required, otherwise None
    def open_order_processing(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: MyScalpStrategy,
            **inputs
    ):

        runner_book = market_book.runners[runner_index]

        # validate wall price is there
        if not validate_wall(
            publish_time=market_book.publish_time,
            runner_book=runner_book,
            trade_tracker=trade_tracker,
            strategy=strategy,
            **inputs
        ):
            return [mytrading.trademachine.tradestates.TradeStates.BIN, mytrading.trademachine.tradestates.TradeStates.PENDING, mytrading.trademachine.tradestates.TradeStates.HEDGE_PLACE_TAKE]

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
            f'replacing active order at price {trade_tracker.active_order.order_type.price} with new price {new_price}',
            market_book.publish_time,
            display_odds=new_price
        )

        # wait for pending to complete then return to this state
        return [mytrading.trademachine.tradestates.TradeStates.PENDING, mytrading.trademachine.tradestates.TradeStates.OPEN_MATCHING]


class WallTradeStateHedgeSelect(mytrading.trademachine.tradestates.TradeStateHedgeSelect):
    """
    select wall hedge trade placement state
    """
    next_state = WallTradeStates.WALL_HEDGE_PLACE


class WallTradeStateHedgeOffset(mytrading.trademachine.tradestates.TradeStateHedgePlaceTake):
    """
    place hedge at number of ticks away from open price
    """
    name = WallTradeStates.WALL_HEDGE_PLACE
    next_state = WallTradeStates.WALL_HEDGE_MATCHING

    def __init__(
            self,
            tick_target,
            min_hedge_price,
            name: WallTradeStates = None,
            next_state: WallTradeStates = None,
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


class WallTradeStateHedgeWait(mytrading.trademachine.tradestates.TradeStateBase):
    """
    wait for hedge to complete, if wall disappears then take available price
    """

    name = WallTradeStates.WALL_HEDGE_MATCHING
    next_state = mytrading.trademachine.tradestates.TradeStates.CLEANING

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: MyScalpStrategy,
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
                strategy,
                **inputs) or order.status in mytrading.trademachine.tradestates.order_error_states:
            trade_tracker.log_update(
                f'wall validation failed, binning trade then taking available',
                market_book.publish_time
            )
            # if wall has gone or error then abandon position and take whatever is available to hedge
            return [
                mytrading.trademachine.tradestates.TradeStates.BIN,
                mytrading.trademachine.tradestates.TradeStates.PENDING,
                mytrading.trademachine.tradestates.TradeStates.HEDGE_PLACE_TAKE
            ]


from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook


from myutils import betting, generic
from myutils import bf_trademachine as bftm, statemachine as stm
from myutils import bf_utils as bfu
from myutils.bf_strategy import MyFeatureData, MyFeatureStrategy
from myutils.generic import  i_prev, i_next
from myutils.bf_types import BfLadderPoint, get_ladder_point
import logging
from typing import List, Dict
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


@dataclass
class WallTradeTracker(bftm.TradeTracker):
    wall: BfLadderPoint = field(default=None)


class WallTradeStateCollection:
    pass


class WallTradeStates(Enum):
    WALL_HEDGE_MATCHING = 'wall hedge trading matching'


class MyScalpStrategy(MyFeatureStrategy):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trade_trackers: Dict[str, Dict[int, List[bftm.TradeTracker]]] = dict()
        self.state_machines: Dict[str, Dict[int, stm.StateMachine]] = dict()

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
    min_hedge_pence = 50

    # maximum spread in ticks between back and lay
    max_tick_spread = 10

    def market_initialisation(self, market: Market, market_book: MarketBook, feature_data: MyFeatureData):
        self.trade_trackers[market.market_id] = dict()
        self.state_machines[market.market_id] = dict()

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

    def get_state_machine(self, selection_id) -> stm.StateMachine:
        """
        get trading state machine for selected runner
        """

        return bftm.RunnerStateMachine(
            states={
                state.name: state
                for state in [
                    WallTradeStateIdle(),
                    WallTradeStateOpenPlace(),
                    WallTradeStateOpenMatching(),
                    bftm.TradeStateBin(),
                    bftm.TradeStatePending(),
                    bftm.TradeStateHedgeSelect(),
                    WallTradeStateHedgeOffset(
                        tick_target=self.tick_target,
                        min_hedge_pence=self.min_hedge_pence
                    ),
                    WallTradeStateHedgeWait(),
                ]
            },
            initial_state=bftm.TradeStateIdle.name,
            selection_id=selection_id,
        )

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:

        # get feature data
        feature_data = self.process_get_feature_data(market, market_book)

        # print(f'{len(feature_data.market_books):5} books processed')

        for runner_index, runner in enumerate(market_book.runners):
            if runner.selection_id not in self.trade_trackers:
                self.trade_trackers[market.market_id][runner.selection_id] = [WallTradeTracker(
                    selection_id=runner.selection_id
                )]
                self.state_machines[market.market_id][runner.selection_id] = self.get_state_machine(
                    runner.selection_id
                )

            trade_tracker = self.trade_trackers[market.market_id][runner.selection_id][-1]
            state_machine = self.state_machines[market.market_id][runner.selection_id]

            runner_book = market_book.runners[runner_index]

            wall_point = self.get_wall(runner_book)

            state_machine.run(
                market_book=market_book,
                market=market,
                runner_index=runner_index,
                trade_tracker=trade_tracker,
                strategy=self,
                wall_point=wall_point
            )


# idle state, waiting to open trade, need to implemeneting sub-classes trade_criteria()
class WallTradeStateIdle(bftm.TradeStateIdle):

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
            spread = bfu.runner_spread(market_book.runners[runner_index].ex)
            if spread <= strategy.max_tick_spread:
                trade_tracker.log(
                    f'detected wall {inputs["wall_point"]}, spread {spread}',
                    market_book.publish_time
                )
                return True


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
    if inputs.get('wall_point') is None:
        trade_tracker.log(
            f'wall variables not detected/invalid: "{inputs.get("wall_point")}"',
            publish_time
        )
        return False

    # get ladder on side of book at which order was placed
    available = bfu.select_ladder_side(runner_book.ex, trade_tracker.open_side)

    # limit tick range, if price drifts to much then bet will be cancelled if not matched
    available = available[:strategy.wall_ticks]

    # check wall exists in trade tracker
    if not trade_tracker.wall:
        trade_tracker.log(
            f'no "wall" instance found in trade_tracker',
            publish_time,
            level=logging.WARNING
        )

    # get original wall pricesize at point of placing trade
    wall_price_size = generic.get_object(available, lambda x: x['price'] == trade_tracker.wall.price)

    # if no money at original wall pricesize (or out of wall ticks range) then abort
    if not wall_price_size:
        trade_tracker.log(
            f'no price info detected at wall price {trade_tracker.wall.price}',
            publish_time
        )
        return False

    # if size of bet at wall price has decreased by more than allowed amount for validation then abort
    if wall_price_size['size'] < strategy.wall_validation * trade_tracker.wall.size:
        trade_tracker.log(
            f'current amount at wall price {trade_tracker.wall.price} of £{wall_price_size["size"]} is less than the '
            f'validation multiplier {strategy.wall_validation} of original size {trade_tracker.wall.size}',
            publish_time
        )
        return False

    return True


def get_wall_adjacent(
        wall_side,
        wall_tick_index
):
    """
    compute the new price of wall trade and store in `trade_tracker`, return new price
    - `wall_side` is the ladder side which wall is located
    - `wall_tick` is the index of the wall price in the array of prices (short to long)

    e.g. if `wall_side` is 'BACK' and `wall_tick` is 150 (price of 3.0) then a price of 2.98 (index 149) is returned
    """

    # get index of tick from wall price
    new_tick_index = wall_tick_index

    if wall_side == 'LAY':

        # wall is on lay side, want to back one tick lower
        new_tick_index = i_prev(new_tick_index)

    else:

        # wall is on back side, want to lay one tick higher
        new_tick_index = i_next(new_tick_index, len(betting.TICKS))

    # get price from tick index
    return betting.LTICKS_DECODED[new_tick_index]


# place an opening trade
class WallTradeStateOpenPlace(bftm.TradeStateOpenPlace):

    def place_trade(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: WallTradeTracker,
            strategy: MyScalpStrategy,
            **inputs) -> BetfairOrder:

        # check if wall inputs are in extra kwargs
        if inputs.get('wall_point') is None:
            trade_tracker.log(
                f'wall variables detected not valid: {inputs.get("wall_point")}',
                market_book.publish_time,
                level=logging.WARNING
            )
            return None

        # store current wall inputs in trade tracker for future reference
        wall: BfLadderPoint = inputs['wall_point']
        trade_tracker.wall = wall
        price = get_wall_adjacent(wall.side, wall.tick_index)

        # create and place order
        trade = Trade(
            market_id=market.market_id,
            selection_id=market_book.runners[runner_index].selection_id,
            handicap=market_book.runners[runner_index].handicap,
            strategy=strategy)

        order = trade.create_order(
            side=wall.side,
            order_type=LimitOrder(
                price=price,
                size=strategy.stake_size
            ))
        strategy.place_order(market, order)
        trade_tracker.log(
            f'placing open order at {price} for {strategy.stake_size} on {wall.side} side',
            market_book.publish_time
        )
        return order


# wait for open trade to match
class WallTradeStateOpenMatching(bftm.TradeStateOpenMatching):

    # return new state(s) if different action required, otherwise None
    def open_trade_processing(
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
            return bftm.TradeStates.BIN

        # get > or < comparator for BACK/LAY side selection
        op = bfu.select_operator_side(trade_tracker.open_side)

        wall: BfLadderPoint = inputs['wall_point']

        # better wall available
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

        trade_tracker.log(
            f'replacing active order at price {trade_tracker.active_order.order_type.price} with new price {new_price}',
            market_book.publish_time
        )

        # wait for pending to complete then return to this state
        return [bftm.TradeStates.PENDING, bftm.TradeStates.OPEN_MATCHING]


# place hedge at number of ticks away from open price
class WallTradeStateHedgeOffset(bftm.TradeStateHedgePlaceTake):

    next_state = WallTradeStates.WALL_HEDGE_MATCHING

    def __init__(
            self,
            tick_target,
            min_hedge_pence,
            name: WallTradeStates = None,
            next_state: WallTradeStates = None,
    ):
        super().__init__(name, next_state, min_hedge_pence)
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
            wall_price_index = i_next(wall_price_index, len(betting.LTICKS), increment=self.tick_target)

        else:

            # closing trade on lay side of the book so want smallest odds as possible
            wall_price_index = i_prev(wall_price_index, increment=self.tick_target)

        return betting.LTICKS_DECODED[wall_price_index]


# wait for hedge to complete, if wall disappears then take available price
class WallTradeStateHedgeWait(bftm.TradeStateBase):

    name = WallTradeStates.WALL_HEDGE_MATCHING
    next_state = bftm.TradeStates.CLEANING

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
                **inputs) or order.status in bftm.order_error_states:
            # if wall has gone or error then abandon position and take whatever is available to hedge
            return [bftm.TradeStates.BIN, bftm.TradeStates.HEDGE_PLACE_TAKE]


WallTradeStateCollection.WallTradeStateIdle = WallTradeStateIdle
WallTradeStateCollection.WallTradeStateOpenPlace = WallTradeStateOpenPlace
WallTradeStateCollection.WallTradeStateOpenMatching = WallTradeStateOpenMatching
WallTradeStateCollection.WallTradeStateHedgeOffset = WallTradeStateHedgeOffset
WallTradeStateCollection.WallTradeStateHedgeWait = WallTradeStateHedgeWait

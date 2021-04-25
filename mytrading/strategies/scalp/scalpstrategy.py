from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook

from ...strategy.trademachine import tradestates
from mytrading.strategy.trademachine.trademachine import RunnerStateMachine
from ...strategy.strategy import MyFeatureStrategy
from ...process.ladder import BfLadderPoint, get_ladder_point
from . import states as wallstates
from .tradetracker import WallTradeTracker


import logging

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyScalpStrategy(MyFeatureStrategy):
    """
    detect "wall" of money at single price on one side of book that is significantly greater than money on other side of
    book
    place trades one tick ahead of "wall" and try to hedge up a few ticks away for a profit
    if wall disappears then abandon and take available price for greening
    """

    def __init__(self, *args, **kwargs):
        super().__init__('scalp', *args, **kwargs)

    trade_tracker_class = WallTradeTracker

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
    ) -> RunnerStateMachine:
        """
        get trading state machine for selected runner
        """

        return RunnerStateMachine(
            states={
                state.name: state
                for state in [
                    tradestates.TradeStateCreateTrade(),
                    wallstates.WallTradeStateIdle(
                        max_tick_spread=self.max_tick_spread
                    ),
                    wallstates.WallTradeStateOpenPlace(
                        stake_size=self.stake_size
                    ),
                    wallstates.WallTradeStateOpenMatching(
                        wall_ticks=self.wall_ticks,
                        wall_validation=self.wall_validation
                    ),
                    tradestates.TradeStateBin(),
                    tradestates.TradeStatePending(),
                    wallstates.WallTradeStateHedgeSelect(),
                    wallstates.WallTradeStateHedgeOffset(
                        tick_target=self.tick_target,
                        min_hedge_price=self.min_hedge_price
                    ),
                    wallstates.WallTradeStateHedgeWait(
                        wall_ticks=self.wall_ticks,
                        wall_validation=self.wall_validation
                    ),
                    tradestates.TradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price
                    ),
                    tradestates.TradeStateHedgeWaitTake(),
                    tradestates.TradeStateClean()
                ]
            },
            initial_state=tradestates.TradeStateCreateTrade.name,
            selection_id=runner.selection_id,
        )

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:

        # update feature data (calls market_initialisation() if new market)
        self.strategy_process_market_book(market, market_book)

        # loop runners
        for runner_index, runner in enumerate(market_book.runners):

            trade_tracker = self.trade_trackers[market.market_id][runner.selection_id]
            state_machine = self.state_machines[market.market_id][runner.selection_id]
            if self._process_trade_machine(runner, state_machine, trade_tracker):

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



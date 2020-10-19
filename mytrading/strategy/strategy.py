from flumine import clients, BaseStrategy
from flumine.order.order import BaseOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook

from datetime import timedelta, datetime, timezone
import logging
from typing import List, Dict, Optional
from os import path, makedirs
from enum import Enum

from mytrading import bf_trademachine as bftm
from mytrading.feature import feature as bff, window as bfw
from mytrading.feature.feature import RunnerFeatureBase
from mytrading.bf_tradetracker import TradeTracker, serializable_order_info
from mytrading.utils.storage import construct_hist_dir
from myutils.timing import EdgeDetector
from myutils import statemachine as stm
from myutils.json_file import add_to_file


# file extension of order result
EXT_ORDER_RESULT = '.orderresult'
EXT_ORDER_INFO = '.orderinfo'
STRATEGY_DIR = r'D:\Betfair_data\historic_strategies'
active_logger = logging.getLogger(__name__)


def path_result(base_dir, name):
    """get file path for order results, from a base directory"""


def filter_orders(orders, selection_id) -> List[BaseOrder]:
    """
    filter order to those placed on a specific runner identified by `selection_id`
    """
    return [o for o in orders if o.selection_id == selection_id]


class MyBaseStrategy(BaseStrategy):
    """
    Implementation of flumine `BaseStrategy`:
    - check_market_book() checks if book is closed
    - place_order() prints if order validation failed
    """
    def check_market_book(self, market: Market, market_book: MarketBook) -> bool:
        """
        return True (tell flumine to run process_market_book()) only executed if market not closed
        """
        if market_book.status != "CLOSED":
            return True

    # override default place order, this time printing where order validation failed
    # TODO - print reason for validation fail
    def place_order(self, market: Market, order) -> None:
        runner_context = self.get_runner_context(*order.lookup)
        if self.validate_order(runner_context, order):
            runner_context.place()
            market.place_order(order)
        else:
            active_logger.warning(f'order validation failed for "{order.selection_id}"')


class BackTestClientNoMin(clients.BacktestClient):
    """
    flumine back test client with no minimum bet size
    """
    @property
    def min_bet_size(self) -> Optional[float]:
        return 0


class FeatureHolder:
    """
    track feature data for runners in one market

    store:
    - window instances
    - dictionary of features indexed by runner ID, then indexed by feature name {runner ID: {feature name: feature}}
    - list of market books to be passed to features
    """
    def __init__(self):
        self.windows: bfw.Windows = bfw.Windows()
        self.features: Dict[int, Dict[str, bff.RunnerFeatureBase]] = dict()
        self.market_books: List[MarketBook] = []

    def process_market_book(self, market_book: MarketBook):
        """
        update each feature for each runner for a new market book
        N.B. market_book MUST have been added to feature_data.market_books prior to calling this function
        """
        # loop runners
        for runner_index, runner in enumerate(market_book.runners):

            # process each feature for current runner
            for feature in self.features[runner.selection_id].values():
                feature.process_runner(
                    self.market_books,
                    market_book,
                    self.windows,
                    runner_index
                )


class MyFeatureStrategy(MyBaseStrategy):
    """
    Store feature data for each market, providing functionality for updating features when new market_book received
    By default features configuration is left blank so default features are used for each runner, but this can be
    overridden
    """

    # number of seconds before start that trading is stopped and greened up
    cutoff_seconds = 2

    # seconds before race start trading allowed
    pre_seconds = 180

    # feature configuration dict (use defaults)
    features_config = bff.get_default_features_config()

    # trade tracker class
    StrategyTradeTracker = TradeTracker

    # list of states that indicate no trade or anything is active
    inactive_states = [bftm.TradeStates.IDLE, bftm.TradeStates.CLEANING]

    # state transitions to cancel a trade and hedge
    force_hedge_states = [
        bftm.TradeStates.BIN,
        bftm.TradeStates.PENDING,
        bftm.TradeStates.HEDGE_PLACE_TAKE
    ]

    def __init__(self, name, strategy_dir=STRATEGY_DIR, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # strategy name
        self.strategy_name = name

        # start timestamp
        self.timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H_%M_%S')

        # strategies base directory
        self.strategy_dir = strategy_dir

        # hold trade tracker {market ID -> {selection ID -> trade tracker}} dictionary
        self.trade_trackers: Dict[str, Dict[int, TradeTracker]] = dict()

        # hold state machine {market ID -> {selection ID -> state machine}} dictionary
        self.state_machines: Dict[str, Dict[int, stm.StateMachine]] = dict()

        # feature holder {market ID -> feature holder} dictionary
        self.feature_holder: Dict[str, FeatureHolder] = dict()

        # order directory {market ID -> order dir} dictionary
        self.output_dirs: Dict[str, str] = dict()

        # create edge detection for cutoff and trading allowed
        self.cutoff = EdgeDetector(False)
        self.allow = EdgeDetector(False)

    def _update_cutoff(self, market_book: MarketBook):
        """update `cutoff`, denoting whether trading is cutoff (too close to start) based on market book timestamp"""
        self.cutoff.update(market_book.publish_time >=
                           (market_book.market_definition.market_time - timedelta(seconds=self.cutoff_seconds)))

    def _update_allow(self, market_book: MarketBook):
        """update `allow`, denoting if close enough to start of race based on market book timestamp"""
        self.allow.update(market_book.publish_time >=
                            (market_book.market_definition.market_time - timedelta(seconds=self.pre_seconds)))

    def _get_output_dir(self, market_book: MarketBook):
        """get output directory for current market to store files"""

        # get event, dated market path
        market_dir = construct_hist_dir(market_book)

        # combine market path with base strategy dir, strategy name and timestamp
        return path.join(self.strategy_dir, self.strategy_name, self.timestamp, market_dir)

    def _reset_complete_trade(
            self,
            state_machine: bftm.RunnerStateMachine,
            trade_tracker: TradeTracker,
            reset_state: Enum = None):

        # clear existing states from state machine
        state_machine.flush()

        # reset to starting states
        state_machine.force_change([reset_state or state_machine.initial_state_key])

        # reset active order and trade variables
        trade_tracker.active_order = None
        trade_tracker.active_trade = None

    def process_closed_market(self, market: Market, market_book: MarketBook) -> None:
        """log updates of each order in trade_tracker for market close"""

        # check market that is closing is in trade trackers
        if market.market_id not in self.trade_trackers:
            return

        # loop runners
        for selection_id, runner_trade_tracker in self.trade_trackers[market.market_id].items():

            # get file path for order result, using selection ID as file name and order result extension
            file_path = path.join(
                self.output_dirs[market.market_id],
                str(selection_id) + EXT_ORDER_RESULT
            )

            # loop trades
            for trade in runner_trade_tracker.trades:

                # loop orders
                for order in trade.orders:

                    # add betfair order result to order results file
                    order_info = serializable_order_info(order)
                    add_to_file(file_path, order_info)

                    runner_trade_tracker.log_update(
                        msg=f'market closed, runner status "{order.runner_status}"',
                        dt=market_book.publish_time,
                        order=order,
                        trade=trade
                    )

    def market_initialisation(self, market: Market, market_book: MarketBook, feature_holder: FeatureHolder):
        """
        called first time strategy receives a new market
        blank function to be overridden with customisations for market initialisations
        """
        pass

    def create_feature_holder(self, market: Market, market_book: MarketBook) -> FeatureHolder:
        """
        create a `MyFeatureData` instance to track runner features for one market
        (can be overridden to customise features)
        """
        return FeatureHolder()

    def create_state_machine(self, runner: RunnerBook, market: Market, market_book: MarketBook) -> stm.StateMachine:
        raise NotImplementedError

    def create_trade_tracker(self, runner: RunnerBook, market: Market, market_book: MarketBook) -> TradeTracker:

        output_path = path.join(self.output_dirs[market.market_id], market.market_id + EXT_ORDER_INFO)
        return self.StrategyTradeTracker(
            selection_id=runner.selection_id,
            file_path=output_path
        )

    def create_features(
            self,
            runner: RunnerBook,
            feature_holder: FeatureHolder,
            market: Market,
            market_book: MarketBook
    ) -> Dict[str, RunnerFeatureBase]:
        """generate a dictionary of features for a given runner on receiving its first market book"""

        return bff.generate_features(
            selection_id=runner.selection_id,
            book=market_book,
            windows=feature_holder.windows,
            features_config=self.features_config
        )

    def process_trade_machine(
            self,
            runner: RunnerBook,
            state_machine: bftm.RunnerStateMachine,
            trade_tracker: TradeTracker):

        # only run state if past timestamp when trading allowed
        if self.allow.current_value:

            # get key for current state
            cs = state_machine.current_state_key

            # if just passed point where trading has stopped, force hedge trade
            if self.cutoff.rising:
                if cs not in self.inactive_states:
                    active_logger.info(f'forcing "{state_machine.selection_id}" to stop trading and hedge')
                    state_machine.flush()
                    state_machine.force_change(self.force_hedge_states)

            # allow run if not yet reached cutoff point
            if not self.cutoff.current_value:

                # if trade tracker done then create a new one
                if state_machine.current_state_key == bftm.TradeStates.CLEANING:
                    active_logger.info(f'runner "{runner.selection_id}" finished trade, resetting...')
                    self._reset_complete_trade(state_machine, trade_tracker)

                return True

            # allow run if past cutoff point but not yet finished hedging
            if self.cutoff.current_value and cs not in self.inactive_states:
                return True

        return False

    def strategy_process_market_book(self, market: Market, market_book: MarketBook):
        """
        get runner feature data for current market with new `market_book` received
        - if first time market is received then `market_initialisation()` is called
        """

        # update cutoff and trading allowed flags
        self._update_cutoff(market_book)
        self._update_allow(market_book)

        if self.cutoff.rising:
            active_logger.info(f'received cutoff flag at {market_book.publish_time}')

        if self.allow.rising:
            active_logger.info(f'received pre-race trade allow flag at {market_book.publish_time}')

        # check if market has been initialised
        if market.market_id not in self.feature_holder:

            # create and store output directory for current market
            output_dir = self._get_output_dir(market_book)
            makedirs(output_dir, exist_ok=True)
            self.output_dirs[market.market_id] = output_dir

            # create feature holder for market
            feature_holder = self.create_feature_holder(market, market_book)
            self.feature_holder[market.market_id] = feature_holder

            # set empty dicts for market trade tracker and state machines (initialised for runners later)
            self.trade_trackers[market.market_id] = dict()
            self.state_machines[market.market_id] = dict()

            # call user defined further market initialisations
            self.market_initialisation(market, market_book, feature_holder)

        # get feature data instance for current market
        feature_holder = self.feature_holder[market.market_id]

        # if runner doesnt have an element in features dict then add (this must be done before window processing!)
        for runner in market_book.runners:
            if runner.selection_id not in feature_holder.features:
                feature_holder.features[runner.selection_id] = self.create_features(
                    runner=runner,
                    feature_holder=feature_holder,
                    market=market,
                    market_book=market_book
                )

        # append new market book to list
        feature_holder.market_books.append(market_book)

        # update windows
        feature_holder.windows.update_windows(feature_holder.market_books, market_book)

        # process features
        feature_holder.process_market_book(market_book)

        # create trade tracker and state machine if runner not yet initialised
        for runner in market_book.runners:
            if runner.selection_id not in self.trade_trackers[market.market_id]:
                active_logger.info(
                    f'creating state machine and trade tracker for "{runner.selection_id}"'
                )
                self.trade_trackers[market.market_id][runner.selection_id] = self.create_trade_tracker(
                    runner=runner,
                    market=market,
                    market_book=market_book
                )
                self.state_machines[market.market_id][runner.selection_id] = self.create_state_machine(
                    runner=runner,
                    market=market,
                    market_book=market_book
                )
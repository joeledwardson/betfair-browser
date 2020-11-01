from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook

from datetime import timedelta, datetime, timezone
import logging
from typing import Dict
from os import path, makedirs
from enum import Enum

from myutils.timing import EdgeDetector, timing_register
from myutils.jsonfile import add_to_file
from ..trademachine.tradestates import TradeStateTypes
from ..trademachine.trademachine import RunnerStateMachine
from ..feature.features import RunnerFeatureBase
from ..feature.utils import generate_features
from ..feature.featureholder import FeatureHolder
from ..feature.storage import features_to_file, get_feature_file_name
from ..tradetracker.tradetracker import TradeTracker
from ..tradetracker.orderinfo import serializable_order_info
from ..tradetracker.messages import MessageTypes
from ..utils.storage import construct_hist_dir, SUBDIR_STRATEGY_HISTORIC, EXT_ORDER_RESULT
from ..utils.storage import EXT_ORDER_INFO, EXT_STRATEGY_INFO
from .basestrategy import MyBaseStrategy

# number of seconds before start that trading is stopped and greened up
PRE_SECONDS = 180

# seconds before race start trading allowed
CUTOFF_SECONDS = 2


active_logger = logging.getLogger(__name__)


class MyFeatureStrategy(MyBaseStrategy):
    """
    Store feature data for each market, providing functionality for updating features when new market_book received
    By default features configuration is left blank so default features are used for each runner, but this can be
    overridden
    """

    # list of states that indicate no trade or anything is active
    inactive_states = [
        TradeStateTypes.IDLE,
        TradeStateTypes.CLEANING
    ]

    # state transitions to cancel a trade and hedge
    force_hedge_states = [
        TradeStateTypes.BIN,
        TradeStateTypes.PENDING,
        TradeStateTypes.HEDGE_PLACE_TAKE
    ]

    def __init__(
            self,
            name,
            base_dir,
            cutoff_seconds=CUTOFF_SECONDS,
            pre_seconds=PRE_SECONDS,
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)

        self.pre_seconds = pre_seconds
        self.cutoff_seconds = cutoff_seconds

        # strategy name
        self.strategy_name = name

        # strategies base directory
        strategy_base_dir = path.join(base_dir, SUBDIR_STRATEGY_HISTORIC)

        # strategy output dir, create (assume not exist)
        self.strategy_dir = self._get_strategy_dir(strategy_base_dir, name, datetime.now(timezone.utc))
        makedirs(self.strategy_dir, exist_ok=False)

        # write to strategy info file
        strategy_file_path = path.join(self.strategy_dir, EXT_STRATEGY_INFO)
        active_logger.info(f'writing strategy info to file: "{strategy_file_path}')
        add_to_file(strategy_file_path, self.info)

        # hold trade tracker {market ID -> {selection ID -> trade tracker}} dictionary
        self.trade_trackers: Dict[str, Dict[int, TradeTracker]] = dict()

        # hold state machine {market ID -> {selection ID -> state machine}} dictionary
        self.state_machines: Dict[str, Dict[int, RunnerStateMachine]] = dict()

        # feature holder {market ID -> feature holder} dictionary
        self.feature_holders: Dict[str, FeatureHolder] = dict()

        # order directory {market ID -> order dir} dictionary
        self.output_dirs: Dict[str, str] = dict()

        # create edge detection for cutoff and trading allowed
        self.cutoff = EdgeDetector(False)
        self.allow = EdgeDetector(False)

    def get_features_config(self, runner: RunnerBook) -> Dict:
        """
        get dictionary of feature configurations to pass to generate_features() and create runner features
        """
        raise NotImplementedError

    def _update_cutoff(self, market_book: MarketBook):
        """
        update `cutoff` instance, denoting whether trading is cutoff (too close to start) based on market book timestamp
        """
        self.cutoff.update(market_book.publish_time >=
                           (market_book.market_definition.market_time - timedelta(seconds=self.cutoff_seconds)))

    def _update_allow(self, market_book: MarketBook):
        """
        update `allow` instance, denoting if close enough to start of race based on market book timestamp
        """
        self.allow.update(market_book.publish_time >=
                            (market_book.market_definition.market_time - timedelta(seconds=self.pre_seconds)))

    def _get_strategy_dir(self, base_dir, name, dt: datetime):
        """
        get strategy output directory to store results
        """
        return path.join(base_dir, name, dt.strftime('%Y-%m-%dT%H_%M_%S'))

    def _get_output_dir(self, market_book: MarketBook):
        """
        get output directory for current market to store files
        """

        # get event, dated market path
        market_dir = construct_hist_dir(market_book)

        # combine strategy dir with market constructed path
        return path.join(self.strategy_dir, market_dir)

    def _get_orderinfo_path(self, market_book: MarketBook):
        """
        get path for order info file for a market
        """
        if market_book.market_id not in self.output_dirs:
            active_logger.critical(f'market ID "{market_book.market_id}" not found in output dirs')
            return ''

        return path.join(
            self.output_dirs[market_book.market_id],
            market_book.market_id + EXT_ORDER_INFO
        )

    def _reset_complete_trade(
            self,
            state_machine: RunnerStateMachine,
            trade_tracker: TradeTracker,
            reset_state: Enum = None):
        """
        process a complete trade by forcing trade machine back to initial state, clearing active order and active trade
        """

        # clear existing states from state machine
        state_machine.flush()

        # reset to starting states
        state_machine.force_change([reset_state or state_machine.initial_state_key])

        # reset active order and trade variables
        trade_tracker.active_order = None
        trade_tracker.active_trade = None

    @timing_register
    def process_closed_market(self, market: Market, market_book: MarketBook) -> None:
        """
        log updates of each order in trade_tracker for market close, in order info tracker, order result and write
        features to file
        """

        # check market that is closing is in trade trackers
        if market.market_id not in self.trade_trackers:
            return

        # check market in output_dirs
        if market_book.market_id not in self.output_dirs:
            active_logger.critical(f'market closed ID "{market_book.market_id}" not found in output dirs')
            return

        # get market output dir
        output_dir = self.output_dirs[market.market_id]

        # loop runners
        for selection_id, runner_trade_tracker in self.trade_trackers[market.market_id].items():

            # check markets exist in features and runner exist in market features
            if market.market_id in self.feature_holders:

                fh = self.feature_holders[market.market_id]
                if selection_id in fh.features:

                    # get runner features and write to file
                    features = fh.features[selection_id]

                    features_file_path = path.join(output_dir, get_feature_file_name(selection_id))
                    active_logger.info(f'writing features for "{selection_id}" to file "{features_file_path}"')
                    features_to_file(features_file_path, features)

            # get file path for order result, using selection ID as file name and order result extension
            file_path = path.join(
                output_dir,
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
                        msg_type=MessageTypes.MARKET_CLOSE,
                        msg_attrs={
                            'runner_status': order.runner_status,
                            'order_id': str(order.id)
                        },
                        dt=market_book.publish_time,
                        order=order,
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

    def create_state_machine(self, runner: RunnerBook, market: Market, market_book: MarketBook) -> RunnerStateMachine:
        """
        create trade state machine for a new runner
        """
        raise NotImplementedError

    def create_trade_tracker(
            self,
            runner: RunnerBook,
            market: Market,
            market_book: MarketBook,
            file_path) -> TradeTracker:
        """
        create a TradeTracker instance for a new runner, taking 'file_path' as argument for trade tracker's order
        info log
        """
        return TradeTracker(
            selection_id=runner.selection_id,
            file_path=file_path
        )

    def create_features(
            self,
            runner: RunnerBook,
            feature_holder: FeatureHolder,
            market: Market,
            market_book: MarketBook
    ) -> Dict[str, RunnerFeatureBase]:
        """
        generate a dictionary of features for a given runner on receiving its first market book
        """

        return generate_features(
            selection_id=runner.selection_id,
            book=market_book,
            windows=feature_holder.windows,
            feature_configs=self.get_features_config(runner)
        )

    def process_trade_machine(
            self,
            publish_time: datetime,
            runner: RunnerBook,
            state_machine: RunnerStateMachine,
            trade_tracker: TradeTracker) -> bool:

        # only run state if past timestamp when trading allowed
        if self.allow.current_value:

            # get key for current state
            cs = state_machine.current_state_key

            # if just passed point where trading has stopped, force hedge trade
            if self.cutoff.rising:

                # log cutoff point
                trade_tracker.log_update(
                    msg_type=MessageTypes.CUTOFF_REACHED,
                    dt=publish_time
                )

                if cs not in self.inactive_states:
                    active_logger.info(f'forcing "{state_machine.selection_id}" to stop trading and hedge')
                    state_machine.flush()
                    state_machine.force_change(self.force_hedge_states)

            # allow run if not yet reached cutoff point
            if not self.cutoff.current_value:

                # if trade tracker done then create a new one
                if state_machine.current_state_key == TradeStateTypes.CLEANING:
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
        if market.market_id not in self.feature_holders:

            # create and store output directory for current market
            output_dir = self._get_output_dir(market_book)
            makedirs(output_dir, exist_ok=True)
            self.output_dirs[market.market_id] = output_dir

            # create feature holder for market
            feature_holder = self.create_feature_holder(market, market_book)
            self.feature_holders[market.market_id] = feature_holder

            # set empty dicts for market trade tracker and state machines (initialised for runners later)
            self.trade_trackers[market.market_id] = dict()
            self.state_machines[market.market_id] = dict()

            # call user defined further market initialisations
            self.market_initialisation(market, market_book, feature_holder)

        # get feature data instance for current market
        feature_holder = self.feature_holders[market.market_id]

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

                # get order info path from market book
                file_path = self._get_orderinfo_path(market_book)

                # create trade tracker for runner
                self.trade_trackers[market.market_id][runner.selection_id] = self.create_trade_tracker(
                    runner=runner,
                    market=market,
                    market_book=market_book,
                    file_path=file_path
                )

                # create state machine for runner
                self.state_machines[market.market_id][runner.selection_id] = self.create_state_machine(
                    runner=runner,
                    market=market,
                    market_book=market_book
                )
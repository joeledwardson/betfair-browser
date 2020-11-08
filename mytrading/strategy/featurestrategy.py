from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook

from datetime import timedelta, datetime, timezone
import logging
from typing import Dict, List
from os import path, makedirs
from enum import Enum

from myutils.timing import EdgeDetector, timing_register
from myutils.jsonfile import add_to_file
from ..process.prices import best_price
from ..trademachine.tradestates import TradeStateTypes
from ..trademachine.trademachine import RunnerStateMachine
from ..feature.features import RunnerFeatureBase
from ..feature.utils import generate_features, get_max_buffer_s
from ..feature.featureholder import FeatureHolder
from ..feature.storage import features_to_file, get_feature_file_name
from ..tradetracker.tradetracker import TradeTracker
from ..tradetracker.orderinfo import serializable_order_info
from ..tradetracker.messages import MessageTypes
from ..utils.storage import construct_hist_dir, SUBDIR_STRATEGY_HISTORIC, EXT_ORDER_RESULT
from ..utils.storage import EXT_ORDER_INFO, EXT_STRATEGY_INFO
from .basestrategy import MyBaseStrategy


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
            cutoff_seconds,
            pre_seconds,
            buffer_seconds,
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)

        self.pre_seconds = pre_seconds
        self.cutoff_seconds = cutoff_seconds
        self.buffer_seconds = buffer_seconds

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

        # hold trade tracker (market ID -> selection ID -> trade tracker) dictionary
        self.trade_trackers: Dict[str, Dict[int, TradeTracker]] = dict()

        # hold state machine (market ID -> selection ID -> state machine) dictionary
        self.state_machines: Dict[str, Dict[int, RunnerStateMachine]] = dict()

        # feature holder (market ID -> feature holder) dictionary
        self.feature_holders: Dict[str, FeatureHolder] = dict()

        # order directory (market ID -> order dir) dictionary
        self.output_dirs: Dict[str, str] = dict()

        # create edge detection for cutoff and trading allowed, and feature processing, (market ID -> EdgeDetector)
        self.flag_cutoff: Dict[str, EdgeDetector] = dict()
        self.flag_allow: Dict[str, EdgeDetector] = dict()
        self.flag_feature: Dict[str, EdgeDetector] = dict()

        # list of tracked markets
        self.tracked_markets: List[str] = []

    def _update_flag_feature(self, market_book: MarketBook):
        """
        update `feature` flag instance, denoting if features should be processed yet

        Parameters
        ----------
        market_book :

        Returns
        -------

        """

        edge_detector = self.flag_feature[market_book.market_id]
        if not edge_detector.current_value:

            # get dictionary of (runner ID -> feature name -> feature)
            runner_features_dict = self.feature_holders[market_book.market_id].features

            # check that there is at least 1 runner
            if len(runner_features_dict):

                # take first runner feature dict (feature name -> feature)
                features = next(iter(runner_features_dict.values()))

                # get max buffer for computing features
                max_buffer_s = get_max_buffer_s(features)

                # compute time based on cutoff seconds + feature buffer seconds + computation buffer seconds
                feature_offset_s = self.cutoff_seconds + self.buffer_seconds + max_buffer_s

                edge_detector.update(
                    market_book.publish_time >=
                    (market_book.market_definition.market_time - timedelta(seconds=feature_offset_s))
                )

        if edge_detector.rising:
            active_logger.info(f'market: "{market_book.market_id}", received feature flag at'
                               f' {market_book.publish_time}')

    def _update_flag_cutoff(self, market_book: MarketBook):
        """
        update `cutoff` flag instance, denoting whether trading is cutoff (too close to start) based on market book
        timestamp
        """

        edge_detector = self.flag_feature[market_book.market_id]
        if not edge_detector.current_value:
            edge_detector.update(
                market_book.publish_time >=
                (market_book.market_definition.market_time - timedelta(seconds=self.cutoff_seconds))
            )

        if edge_detector.rising:
            active_logger.info(f'market: "{market_book.market_id}", received cutoff trade allow flag at ' 
                               f'{market_book.publish_time}')

    def _update_flag_allow(self, market_book: MarketBook):
        """
        update `allow` flag instance, denoting if close enough to start of race based on market book timestamp
        """

        edge_detector = self.flag_feature[market_book.market_id]
        if not edge_detector.current_value:
            edge_detector.update(
                market_book.publish_time >=
                (market_book.market_definition.market_time - timedelta(seconds=self.pre_seconds))
            )
        if edge_detector.rising:
            active_logger.info(f'market: "{market_book.market_id}", received allow trade flag at '
                               f'{market_book.publish_time}')

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

    def _market_initialisation(self, market: Market, market_book: MarketBook):
        """
        add market to tracked markets and initialise objects where market ID is key

        - create output directory in self.output_dirs for market (market ID -> output directory)
        - create feature holder for market (market ID -> feature holder)
        - create empty dict market trade tracker (market ID -> selection ID -> trade tracker)
        - create empty dict market state machine (market ID -> selection ID -> state machine)

        - create flag instances for cutoff, trading allowed, and feature processing (market ID -> EdgeDetector)

        Returns
        -------

        """
        # add market to tracked list
        self.tracked_markets.append(market.market_id)

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

        # create flag instances
        self.flag_allow[market.market_id] = EdgeDetector(False)
        self.flag_cutoff[market.market_id] = EdgeDetector(False)
        self.flag_feature[market.market_id] = EdgeDetector(False)

    def _runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
        """
        initialise runner first time its RunnerBook is processed in a market

        - create trade tracker within (self.trade_trackers -> market ID -> runner ID)
        - create state machine within (self.state_machines -> market ID -> runner ID)
        - create runner features within feature holder (self.feature_holders -> market ID -> runner ID) and run race
        initialiser for each feature

        Parameters
        ----------
        market :
        market_book :

        Returns
        -------

        """
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

        # create runner features
        features = self.create_runner_features()

        # get feature holder for market
        feature_holder = self.feature_holders[market.market_id]

        # initialise for race
        for feature in features.values():
            feature.race_initializer(runner.selection_id, market_book, feature_holder.windows)

        # set feature dict to feature holder
        self.feature_holders[market.market_id].features[runner.selection_id] = features

        # user runner initialization
        self.runner_initialisation(market, market_book, runner)

    def _update_feature_holder(self, feature_holder: FeatureHolder, market_book: MarketBook):
        """
        update FeatureHolder instance for a market with new market book

        Parameters
        ----------
        feature_holder :

        Returns
        -------

        """

        # append new market book to list
        feature_holder.market_books.append(market_book)

        # update windows
        feature_holder.windows.update_windows(feature_holder.market_books, market_book)

        # process features
        feature_holder.process_market_book(market_book)

    def _process_trade_machine(
            self,
            market_book: MarketBook,
            runner: RunnerBook
    ) -> bool:
        """
        determine whether to run state machine for a given runner, if past allow trading point value and not past
        cutoff point.

        when reaching cutoff point, will force states to cancel active trade and hedge. Also, will return true if
        past cutoff point but not finished hedging active trade

        Parameters
        ----------
        runner :

        Returns
        -------

        """

        state_machine = self.state_machines[market_book.market_id][runner.selection_id]
        trade_tracker = self.trade_trackers[market_book.market_id][runner.selection_id]

        # check if first book received where allowed to trade
        if self.flag_allow[market_book.market_id].rising:

            # set display odds as either LTP/best back/best lay depending if any/all are available
            ltp = runner.last_price_traded
            best_back = best_price(runner.ex.available_to_back)
            best_lay = best_price(runner.ex.available_to_lay)
            display_odds = ltp or best_back or best_lay or 0

            # log message
            trade_tracker.log_update(
                msg_type=MessageTypes.MSG_ALLOW_REACHED,
                dt=market_book.publish_time,
                msg_attrs={
                    'pre_seconds': self.pre_seconds,
                    'start_time': market_book.market_definition.market_time.isoformat()
                },
                display_odds=display_odds
            )

        # only run state if past timestamp when trading allowed
        if self.flag_allow[market_book.market_id].current_value:

            # get key for current state
            cs = state_machine.current_state_key

            # if just passed point where trading has stopped, force hedge trade
            if self.flag_cutoff[market_book.market_id].rising:

                # log cutoff point
                trade_tracker.log_update(
                    msg_type=MessageTypes.MSG_CUTOFF_REACHED,
                    dt=market_book.publish_time,
                    msg_attrs={
                        'cutoff_seconds': self.cutoff_seconds,
                        'start_time': market_book.market_definition.market_time.isoformat()
                    }
                )

                if cs not in self.inactive_states:
                    active_logger.info(f'forcing "{state_machine.selection_id}" to stop trading and hedge')
                    state_machine.flush()
                    state_machine.force_change(self.force_hedge_states)

            # allow run if not yet reached cutoff point
            if not self.flag_cutoff[market_book.market_id].current_value:

                # if trade tracker done then create a new one
                if state_machine.current_state_key == TradeStateTypes.CLEANING:
                    active_logger.info(f'runner "{runner.selection_id}" finished trade, resetting...')
                    self._reset_complete_trade(state_machine, trade_tracker)

                return True

            # allow run if past cutoff point but not yet finished hedging
            if self.flag_cutoff[market_book.market_id].current_value and cs not in self.inactive_states:
                return True

        return False

    def market_initialisation(self, market: Market, market_book: MarketBook, feature_holder: FeatureHolder):
        """
        called first time strategy receives a new market
        blank function to be overridden with customisations for market initialisations
        """
        pass

    def runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
        """
        optional initialisation the first time a runner book is processed for a market (not including feature
        processing)

        Returns
        -------

        """
        pass

    def create_feature_holder(self, market: Market, market_book: MarketBook) -> FeatureHolder:
        """
        create a `MyFeatureData` instance to track runner features for one market
        (can be overridden to customise features)
        """
        return FeatureHolder()

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

    def create_runner_features(self) -> Dict[str, RunnerFeatureBase]:
        """
        generate a dictionary of features for a given runner on receiving its first market book
        """

        return generate_features(
            feature_configs=self.get_features_config()
        )

    def get_features_config(self) -> Dict:
        """
        get dictionary of feature configurations to pass to generate_features() and create runner features
        """
        raise NotImplementedError

    def trade_machine_kwargs(
            self,
            market: Market,
            market_book: MarketBook,
            runner_index: int,
    ) -> dict:
        """

        Parameters
        ----------
        market :
        market_book :
        runner_index :

        Returns
        -------

        """
        raise NotImplementedError

    def create_state_machine(self, runner: RunnerBook, market: Market, market_book: MarketBook) -> RunnerStateMachine:
        """
        create trade state machine for a new runner
        """
        raise NotImplementedError

    @timing_register
    def process_market_book(self, market: Market, market_book: MarketBook):
        """
        get runner feature data for current market with new `market_book` received
        - if first time market is received then `market_initialisation()` is called
        """

        assert(market.market_id == market_book.market_id and
               f'expected market id "{market.market_id}" to be the same as market book id "{market_book.market_id}"')

        # check if market has been initialised
        if market.market_id not in self.tracked_markets:
            self._market_initialisation(market, market_book)

        # update flags
        self._update_flag_feature(market_book)
        self._update_flag_allow(market_book)
        self._update_flag_cutoff(market_book)

        # check that features are to be processed
        if self.flag_feature[market.market_id].current_value:

            # loop runners
            for runner in market_book.runners:

                # initialise runner trade tracker, trade machine and features if not initialised (assume runner not
                # in trade trackers means not in state machine or feature either)
                if runner.selection_id not in self.trade_trackers[market.market_id]:
                    self._runner_initialisation(market, market_book, runner)

            # update feature holder instance for market
            self._update_feature_holder(self.feature_holders[market.market_id], market_book)

        # check if trading is to be performed (features flag *should* always be true if allow flag is)
        if self.flag_allow[market.market_id].current_value and self.flag_feature[market.market_id].current_value:

            # loop runners
            for runner_index, runner in enumerate(market_book.runners):

                # check if runner is being tracked
                if runner.selection_id not in self.trade_trackers[market.market_id]:
                    self._runner_initialisation(market, market_book, runner)

                # get trade tracker, state machine for runner
                trade_tracker = self.trade_trackers[market.market_id][runner.selection_id]
                state_machine = self.state_machines[market.market_id][runner.selection_id]

                # check if state machine is to be run
                if self._process_trade_machine(market_book, runner):

                    # get feature specific state machine kwargs
                    additional_kwargs = self.trade_machine_kwargs(market, market_book, runner_index)

                    state_machine.run(
                        market_book=market_book,
                        market=market,
                        runner_index=runner_index,
                        trade_tracker=trade_tracker,
                        strategy=self,
                        **additional_kwargs
                    )

                # update order tracker
                trade_tracker.update_order_tracker(market_book.publish_time)

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
                        msg_type=MessageTypes.MSG_MARKET_CLOSE,
                        msg_attrs={
                            'runner_status': order.runner_status,
                            'order_id': str(order.id)
                        },
                        dt=market_book.publish_time,
                        order=order,
                    )

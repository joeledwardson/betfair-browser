import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from os import path, makedirs
from typing import Optional, Dict, List
import logging

from betfairlightweight.resources import MarketBook, RunnerBook
from flumine import clients, BaseStrategy
from flumine.markets.market import Market

from ..process.prices import best_price
from .feature import RFBase, FeatureHolder
from .trademachine.trademachine import RunnerStateMachine
from.trademachine.tradestates import TradeStateTypes
from.tradetracker.messages import MessageTypes
from.tradetracker.tradetracker import TradeTracker
from ..utils.storage import SUBDIR_RECORDED, construct_hist_dir, EXT_CATALOGUE, EXT_RECORDED
from myutils.mytiming import EdgeDetector, timing_register

active_logger = logging.getLogger(__name__)


class BackTestClientNoMin(clients.BacktestClient):
    """flumine back test client with no minimum bet size"""
    @property
    def min_bet_size(self) -> Optional[float]:
        return 0


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
    def place_order(self, market: Market, order, market_version: int = None) -> None:
        runner_context = self.get_runner_context(*order.lookup)
        if self.validate_order(runner_context, order):
            runner_context.place(order.trade.id)
            market.place_order(order)
        else:
            active_logger.warning(f'order validation failed for "{order.selection_id}"')


# TODO - make this work with database, update from old storage convention
class MyRecorderStrategy(BaseStrategy):
    """
    Record streaming updates by writing to file

    Would make more sense to use `process_raw_data` but would have to configure a stream from
    `flumine.streams.datastream.FlumineStream` which produces `RawDataEvent`
    However, by default strategies use `flumine.streams.marketstream.MarketStream` which does not use this and I'm
    not sure how to combine the two streams, whereby the `MarketStream` produces `MarketBook` updates but also raw
    data so just going to process from market books
    """
    def __init__(self, base_dir, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_dir = base_dir
        self.market_paths = {}
        self.catalogue_paths = {}

    def check_market_book(self, market: Market, market_book: MarketBook) -> bool:
        return True

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:
        market_id = market_book.market_id

        if market_id not in self.catalogue_paths and market.market_catalogue:

            # make sure dir exists
            dir_path = path.join(
                self.base_dir,
                SUBDIR_RECORDED,
                construct_hist_dir(market_book)
            )
            makedirs(dir_path, exist_ok=True)

            # store catalogue
            catalogue_path = path.join(
                dir_path,
                market_id + EXT_CATALOGUE
            )
            self.catalogue_paths[market_id] = catalogue_path
            active_logger.info(f'writing market id "{market_id}" catalogue to "{catalogue_path}"')
            with open(catalogue_path, 'w') as file_catalogue:
                file_catalogue.write(market.market_catalogue.json())

        if market_id not in self.market_paths:

            # create directory for historical market
            dir_path = path.join(
                self.base_dir,
                SUBDIR_RECORDED,
                construct_hist_dir(market_book)
            )
            makedirs(dir_path, exist_ok=True)

            # get path for historical file where market data to be stored
            market_path = path.join(
                dir_path,
                market_id + EXT_RECORDED
            )
            self.market_paths[market_id] = market_path
            active_logger.info(f'new market started recording: "{market_id}" to {market_path}')

        # convert datetime to milliseconds since epoch
        pt = int((market_book.publish_time - datetime.utcfromtimestamp(0)).total_seconds() * 1000)

        # construct data in historical format
        update = {
            'op': 'mcm',
            'clk': None,
            'pt': pt,
            'mc': [market_book.streaming_update]
        }

        # convert to string and add newline
        update = json.dumps(update) + '\n'

        # write to file
        with open(self.market_paths[market_id], 'a') as f:
            f.write(update)

# TODO - roll other strategy files into this one, merge orderinfo/tradefollwer into tradetracker file,
#  collapse trademachine package, collapse tradetracker package, features can still be in own package with global
#  desf like FeatureHolder and FeatureCfgUtils in __init__

# TODO - could this be merged with tradetracker?
class RunnerHandler:

    def __init__(self, trade_tracker: TradeTracker, state_machine: RunnerStateMachine, features: Dict[str, RFBase]):
        self.features: Dict[str, RFBase] = features
        self.trade_tracker = trade_tracker
        self.state_machine = state_machine


class MarketHandler:

    def __init__(self):

        # create flag instances
        self.flag_allow = EdgeDetector(False)
        self.flag_cutoff = EdgeDetector(False)
        self.flag_feature = EdgeDetector(False)

        # runners
        self.runner_handlers: Dict[int, RunnerHandler] = dict()

        # TODO - remove? bad practice to store all books
        self.market_books: List[MarketBook] = []
        self.closed = False

    def update_flag_feature(self, market_book: MarketBook, feature_seconds):
        """
        update `feature` flag instance, denoting if features should be processed yet
        """
        self.flag_feature.update(
            market_book.publish_time >=
            (market_book.market_definition.market_time - timedelta(seconds=feature_seconds))
        )

        if self.flag_feature.rising:
            active_logger.info(f'market: "{market_book.market_id}", received feature flag at'
                               f' {market_book.publish_time}')

    def update_flag_cutoff(self, market_book: MarketBook, cutoff_seconds):
        """
        update `cutoff` flag instance, denoting whether trading is cutoff (too close to start) based on market book
        timestamp
        """

        self.flag_cutoff.update(
            market_book.publish_time >=
            (market_book.market_definition.market_time - timedelta(seconds=cutoff_seconds))
        )

        if self.flag_cutoff.rising:
            active_logger.info(f'market: "{market_book.market_id}", received cutoff trade allow flag at ' 
                               f'{market_book.publish_time}')

    def update_flag_allow(self, market_book: MarketBook, pre_seconds):
        """
        update `allow` flag instance, denoting if close enough to start of race based on market book timestamp
        """

        self.flag_allow.update(
            market_book.publish_time >=
            (market_book.market_definition.market_time - timedelta(seconds=pre_seconds))
        )
        if self.flag_allow.rising:
            active_logger.info(f'market: "{market_book.market_id}", received allow trade flag at '
                               f'{market_book.publish_time}')


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
        TradeStateTypes.HEDGE_TAKE_PLACE
    ]

    def __init__(
            self,
            name: str,
            base_dir: str,
            cutoff_seconds: int,
            pre_seconds: int,
            feature_seconds: int,
            historic: bool,
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)

        self.strategy_id = uuid.uuid4()
        self.pre_seconds = pre_seconds
        self.cutoff_seconds = cutoff_seconds
        self.feature_seconds = feature_seconds

        # strategy name
        self.strategy_name = name

        # TODO update directories
        # strategies base directory
        self.base_dir = base_dir
        self.market_handlers: Dict[str, MarketHandler] = dict()

        # self.max_order_count: MaxOrderCount = [ctrl for ctrl in self.client.trading_controls
        #                                        if ctrl.NAME == "MAX_ORDER_COUNT"][0]

    def write_strategy_kwargs(self, indent=4):

        # check no args passed
        if self.strategy_args:
            raise Exception('please pass kwargs only to strategy so they can logged in strategy config file')

        # check kwargs passed
        if not self.strategy_kwargs:
            raise Exception('if writing strategy kwargs, please ensure "store_kwargs" wraps constructor with '
                            'key_kwargs="strategy_kwargs" set')

        # write to strategy info file
        meta_path = path.join(self.base_dir, 'strategymeta', str(self.strategy_id), 'info')
        active_logger.info(f'writing strategy info to file: "{meta_path}')
        d, _ = path.split(meta_path)
        makedirs(d)
        with open(meta_path, 'w') as f:
            f.write(json.dumps(self.strategy_kwargs, indent=indent))

    def _reset_complete_trade(self, runner_handler: RunnerHandler, reset_state: Enum = None):
        """
        process a complete trade by forcing trade machine back to initial state, clearing active order and active trade
        """

        # clear existing states from state machine
        runner_handler.state_machine.flush()

        # reset to starting states
        runner_handler.state_machine.force_change([reset_state or runner_handler.state_machine.initial_state_key])

        # reset active order and trade variables
        runner_handler.trade_tracker.active_order = None
        runner_handler.trade_tracker.active_trade = None

    # TODO - should this be in runner handler?
    def _process_trade_machine(
            self,
            market_book: MarketBook,
            runner: RunnerBook,
            market_handler: MarketHandler,
            runner_handler: RunnerHandler,
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

        state_machine = runner_handler.state_machine
        trade_tracker = runner_handler.trade_tracker

        # check if first book received where allowed to trade
        if market_handler.flag_allow.rising:

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
        if market_handler.flag_allow.current_value:

            # get key for current state
            cs = state_machine.current_state_key

            # if just passed point where trading has stopped, force hedge trade
            if market_handler.flag_cutoff.rising:

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
            if not market_handler.flag_cutoff.current_value:

                # if trade tracker done then create a new one
                if state_machine.current_state_key == TradeStateTypes.CLEANING:
                    active_logger.info(f'runner "{runner.selection_id}" finished trade, resetting...')
                    self._reset_complete_trade(runner_handler)

                return True

            # allow run if past cutoff point but not yet finished hedging
            if market_handler.flag_cutoff.current_value and cs not in self.inactive_states:
                return True

        return False

    def custom_market_initialisation(self, market: Market, market_book: MarketBook):
        """
        called first time strategy receives a new market
        blank function to be overridden with customisations for market initialisations
        """
        pass

    def custom_runner_initialisation(self, market: Market, market_book: MarketBook, runner: RunnerBook):
        """
        optional initialisation the first time a runner book is processed for a market (not including feature
        processing)

        Returns
        -------

        """
        pass

    def get_features_config(self, market: Market, market_book: MarketBook, runner_index) -> Dict:
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

    def create_trade_tracker(
            self,
            market: Market,
            market_book: MarketBook,
            runner: RunnerBook,
            file_path: str) -> TradeTracker:
        """
        create a TradeTracker instance for a new runner, taking 'file_path' as argument for trade tracker's order
        info log
        """
        return TradeTracker(
            selection_id=runner.selection_id,
            file_path=file_path
        )

    def create_state_machine(self, runner: RunnerBook, market: Market, market_book: MarketBook) -> RunnerStateMachine:
        """
        create trade state machine for a new runner
        """
        raise NotImplementedError

    def process_runner_features(self, mb: MarketBook, mh: MarketHandler, selection_id, runner_index):
        """
        process features for a given runner
        """

        # process each feature for current runner
        for feature in mh.runner_handlers[selection_id].features.values():
            feature.process_runner(mb, runner_index)

    @timing_register
    def process_market_book(self, market: Market, market_book: MarketBook):
        """
        get runner feature data for current market with new `market_book` received
        - if first time market is received then `market_initialisation()` is called
        """

        assert(market.market_id == market_book.market_id and
               f'expected market id "{market.market_id}" to be the same as market book id "{market_book.market_id}"')

        # check if market has been initialised
        udpt_dir = path.join(self.base_dir, 'strategyupdates', str(self.strategy_id), market_book.market_id)
        if market.market_id not in self.market_handlers:
            makedirs(udpt_dir)
            self.market_handlers[market.market_id] = MarketHandler()
            self.custom_market_initialisation(market, market_book)

        mh = self.market_handlers[market.market_id]
        if mh.closed:
            active_logger.warning(f'process_market_book called on market "{market.market_id}" which is closed already')
            return

        # update flags
        mh.update_flag_feature(market_book, self.feature_seconds)
        mh.update_flag_allow(market_book, self.pre_seconds)
        mh.update_flag_cutoff(market_book, self.cutoff_seconds)

        # check that features are to be processed
        if mh.flag_feature.current_value:

            # loop runners
            for runner_index, runner in enumerate(market_book.runners):

                # initialiase runner if not tracked
                if runner.selection_id not in mh.runner_handlers:

                    # create runner features
                    features = FeatureHolder.gen_ftrs(
                        ftr_cfgs=self.get_features_config(market, market_book, runner_index)
                    )

                    # initialise for race
                    for feature in features.values():
                        feature.race_initializer(runner.selection_id, market_book)

                    udt_path = path.join(udpt_dir, 'updates')
                    mh.runner_handlers[runner.selection_id] = RunnerHandler(
                        trade_tracker=self.create_trade_tracker(market, market_book, runner, udt_path),
                        state_machine=self.create_state_machine(runner, market, market_book),
                        features=features
                    )

                    # user runner initialization and assign to runner handler list
                    self.custom_runner_initialisation(market, market_book, runner)

            # append new market book to list
            mh.market_books.append(market_book)

            # process runner features
            for runner_index, runner in enumerate(market_book.runners):
                self.process_runner_features(market_book, mh, runner.selection_id, runner_index)

        # check if trading is to be performed (features flag *should* always be true if allow flag is)
        if mh.flag_allow.current_value and mh.flag_feature.current_value:

            # loop runners
            for runner_index, runner in enumerate(market_book.runners):

                # get trade tracker, state machine for runner
                rh = mh.runner_handlers[runner.selection_id]

                # check if state machine is to be run
                if self._process_trade_machine(market_book, runner, mh, rh):

                    # get feature specific state machine kwargs
                    additional_kwargs = self.trade_machine_kwargs(market, market_book, runner_index)

                    rh.state_machine.run(
                        market_book=market_book,
                        market=market,
                        runner_index=runner_index,
                        trade_tracker=rh.trade_tracker,
                        strategy=self,
                        **additional_kwargs
                    )

                # update order tracker
                rh.trade_tracker.update_order_tracker(market_book.publish_time)

    @timing_register
    def process_closed_market(self, market: Market, market_book: MarketBook) -> None:
        """
        log updates of each order in trade_tracker for market close, in order info tracker, order result and write
        features to file
        """

        # check market that is closing is in trade trackers
        if market.market_id not in self.market_handlers:
            active_logger.warning(f'market ID "{market.market_id}" closing but not tracked')
            return

        # check market hasn't already been closed
        mh = self.market_handlers[market.market_id]
        if mh.closed:
            active_logger.warning(f'market ID "{market.market_id}" already closed')
            return

        mh.closed = True

        # loop runners
        for selection_id, rh in mh.runner_handlers.items():

            # file_name = get_feature_file_name(selection_id)
            # file_path = path.join(mh.output_dir, file_name)
            # active_logger.info(f'writing features for "{selection_id}" to file "{file_path}"')
            # features_to_file(file_path, rh.features)

            # get file path for order result, using selection ID as file name and order result extension
            # file_path = path.join(
            #     mh.output_dir,
            #     str(selection_id) + EXT_ORDER_RESULT
            # )

            # loop trades
            for trade in rh.trade_tracker.trades:

                # loop orders
                for order in trade.orders:

                    # TODO - reset trade ID here to None so market close messages not associated with any trade
                    rh.trade_tracker.log_update(
                        msg_type=MessageTypes.MSG_MARKET_CLOSE,
                        msg_attrs={
                            'runner_status': order.runner_status,
                            'order_id': str(order.id)
                        },
                        dt=market_book.publish_time,
                        order=order,
                    )

        del mh.market_books
        del mh.runner_handlers
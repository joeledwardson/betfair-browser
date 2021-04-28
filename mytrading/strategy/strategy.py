import json
import uuid
from datetime import datetime, timedelta
from os import path, makedirs
from typing import Optional, Dict
import logging
import yaml

from betfairlightweight.resources import MarketBook, RunnerBook
from flumine import clients, BaseStrategy
from flumine.markets.market import Market

from ..exceptions import MyStrategyException
from ..process import get_best_price
from ..utils import bettingdb
from .feature import FeatureHolder
from .trademachine import RunnerStateMachine
from .tradestates import TradeStateTypes
from .messages import MessageTypes
from .tradetracker import TradeTracker
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
    # TODO - trade tracker log reason for validation fail
    def place_order(self, market: Market, order, market_version: int = None) -> None:
        runner_context = self.get_runner_context(*order.lookup)
        if self.validate_order(runner_context, order):
            runner_context.place(order.trade.id)
            market.place_order(order)
        else:
            active_logger.warning(f'order validation failed for "{order.selection_id}"')


# TODO - user data recording process which accepts a function to retrieve custom user data, then writes it into the
#  cache file for USER info in market streaming - each line can have a dictionary of user values which is keyed by
#  the user function name - to pass down to features, could have a class object which is passed to race initialiser
#  on creation
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
        self.db = bettingdb.BettingDB()
        self.base_dir = base_dir
        self.market_paths = {}
        self.catalogue_paths = {}

    def check_market_book(self, market: Market, market_book: MarketBook) -> bool:
        return True

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:
        market_id = market_book.market_id
        if market_id not in self.catalogue_paths and market.market_catalogue:
            # get cache path, create dir if not exist
            p = self.db.cache_col(
                'marketstream',
                {'market_id': market_id},
                'catalogue',
            )
            d, _ = path.split(p)
            makedirs(d, exist_ok=True)
            # store catalogue
            self.catalogue_paths[market_id] = p
            active_logger.info(f'writing market id "{market_id}" catalogue to "{catalogue_path}"')
            with open(p, 'w') as f:
                f.write(market.market_catalogue.json())

        if market_id not in self.market_paths:
            # get cache path, create dir if not exist
            p = self.db.cache_col(
                'marketstream',
                {'market_id': market_id},
                'data'
            )
            d, _ = path.split(p)
            makedirs(d, exist_ok=True)
            # set path var
            self.market_paths[market_id] = p
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


class RunnerHandler:
    def __init__(
            self,
            selection_id: int,
            trade_tracker: TradeTracker,
            state_machine: RunnerStateMachine,
            features: FeatureHolder
    ):
        self.selection_id = selection_id
        self.features: FeatureHolder = features
        self.trade_tracker = trade_tracker
        self.state_machine = state_machine

    def rst_trade(self):
        """process a complete trade by forcing trade machine back to initial state, clearing active order and active
        trade"""

        # clear existing states from state machine
        self.state_machine.flush()

        # reset to starting states
        self.state_machine.force_change([self.state_machine.initial_state_key])

        # reset active order and trade variables
        self.trade_tracker.active_order = None
        self.trade_tracker.active_trade = None

    def msg_allow(self, mbk: MarketBook, rbk: RunnerBook, pre_seconds: float):
        """log message that allow trading point reached"""
        # set display odds as either LTP/best back/best lay depending if any/all are available
        ltp = rbk.last_price_traded
        best_back = get_best_price(rbk.ex.available_to_back)
        best_lay = get_best_price(rbk.ex.available_to_lay)
        display_odds = ltp or best_back or best_lay or 0

        # log message
        self.trade_tracker.log_update(
            msg_type=MessageTypes.MSG_ALLOW_REACHED,
            dt=mbk.publish_time,
            msg_attrs={
                'pre_seconds': pre_seconds,
                'start_time': mbk.market_definition.market_time.isoformat()
            },
            display_odds=display_odds
        )

    def msg_cutoff(self, mbk: MarketBook, cutoff_seconds):
        """log message that reached cutoff point"""
        self.trade_tracker.log_update(
            msg_type=MessageTypes.MSG_CUTOFF_REACHED,
            dt=mbk.publish_time,
            msg_attrs={
                'cutoff_seconds': cutoff_seconds,
                'start_time': mbk.market_definition.market_time.isoformat()
            }
        )

    def force_hedge(self, hedge_states):
        """force state machine to hedge"""
        active_logger.info(f'forcing "{self.selection_id}" to stop trading and hedge')
        self.state_machine.flush()
        self.state_machine.force_change(hedge_states)


class MarketHandler:

    def __init__(self):

        # create flag instances
        self.flag_allow = EdgeDetector(False)
        self.flag_cutoff = EdgeDetector(False)
        self.flag_feature = EdgeDetector(False)

        # runners
        self.runner_handlers: Dict[int, RunnerHandler] = dict()

        # market closed
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


# TODO - write feature data sequentially rather than as massive dictionary at end of processing
class MyFeatureStrategy(MyBaseStrategy):
    """
    Store feature data for each market, providing functionality for updating features when new market_book received
    By default features configuration is left blank so default features are used for each runner, but this can be
    overridden
    """

    # list of states that indicate no trade or anything is active
    INACTIVE_STATES = [
        TradeStateTypes.IDLE,
        TradeStateTypes.CLEANING
    ]

    # state transitions to cancel a trade and hedge
    FORCE_HEDGE_STATES = [
        TradeStateTypes.BIN,
        TradeStateTypes.PENDING,
        TradeStateTypes.HEDGE_TAKE_PLACE
    ]

    def __init__(
            self,
            *,
            name: str,
            base_dir: str,
            cutoff_seconds: int,
            pre_seconds: int,
            feature_seconds: int,
            historic: bool,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.strategy_id = uuid.uuid4()
        self.pre_seconds = pre_seconds
        self.cutoff_seconds = cutoff_seconds
        self.feature_seconds = feature_seconds
        self.strategy_name = name
        # TODO update directories
        # strategies base directory
        self.base_dir = base_dir
        self.market_handlers: Dict[str, MarketHandler] = dict()

    def write_strategy_info(self, init_kwargs):
        """write strategy information to file"""
        info = {
            'name': self.__class__.__name__,
            'kwargs': init_kwargs
        }
        meta_path = path.join(self.base_dir, 'strategymeta', str(self.strategy_id), 'info')
        active_logger.info(f'writing strategy info to file: "{meta_path}')
        d, _ = path.split(meta_path)
        makedirs(d)
        with open(meta_path, 'w') as f:
            f.write(yaml.dump(info))

    def allow_trademachine(
            self,
            mbk: MarketBook,
            rbk: RunnerBook,
            mh: MarketHandler,
            rh: RunnerHandler
    ) -> bool:
        """
        determine whether to run state machine for a given runner, if past allow trading point value and not past
        cutoff point.

        when reaching cutoff point, will force states to cancel active trade and hedge. Also, will return true if
        past cutoff point but not finished hedging active trade
        """

        # check if first book received where allowed to trade
        if mh.flag_allow.rising:
            rh.msg_allow(mbk, rbk, self.pre_seconds)

        # only run state if past timestamp when trading allowed
        if mh.flag_allow.current_value:
            sm = rh.state_machine

            # if just passed point where trading has stopped, force hedge trade
            if mh.flag_cutoff.rising:
                rh.msg_cutoff(mbk, self.cutoff_seconds)
                if sm.current_state_key not in self.INACTIVE_STATES:
                    rh.force_hedge(self.FORCE_HEDGE_STATES)

            # allow run if not yet reached cutoff point
            if not mh.flag_cutoff.current_value:
                # if trade tracker done then create a new one
                if sm.current_state_key == TradeStateTypes.CLEANING:
                    active_logger.info(f'runner "{rbk.selection_id}" finished trade, resetting...')
                    rh.rst_trade()
                return True

            # allow run if past cutoff point but not yet finished hedging
            if mh.flag_cutoff.current_value and sm.current_state_key not in self.INACTIVE_STATES:
                return True

        return False

    def get_featureholder(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int) -> FeatureHolder:
        """generate feature holder dictionary of feature instance for new runner"""
        raise NotImplementedError

    def run_trade_machine(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int):
        """operate runner trade machine given new market book"""
        raise NotImplementedError

    def get_state_machine(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int) -> RunnerStateMachine:
        """create trade state machine for a new runner"""
        raise NotImplementedError

    def process_runner_features(self, mb: MarketBook, mh: MarketHandler, selection_id, runner_index):
        """process features for a given runner for new market book"""
        for feature in mh.runner_handlers[selection_id].features.values():
            feature.process_runner(mb, runner_index)

    def get_runner_handler(
            self,
            mkt: Market,
            mbk: MarketBook,
            rbk: RunnerBook,
            fh: FeatureHolder,
            i: int,
            upth: str,
    ) -> RunnerHandler:
        """create runner handler instance on new runner"""
        return RunnerHandler(
            selection_id=rbk.selection_id,
            trade_tracker=TradeTracker(
                selection_id=rbk.selection_id,
                file_path=upth
            ),
            state_machine=self.get_state_machine(mkt, mbk, rbk, i),
            features=fh
        )

    def get_market_handler(self, mkt: Market, mbk: MarketBook) -> MarketHandler:
        """create market handler, can be overridden to customise market handler instance with more attributes"""
        return MarketHandler()

    @timing_register
    def process_market_book(self, market: Market, market_book: MarketBook):
        """
        get runner feature data for current market with new `market_book` received
        - if first time market is received then `market_initialisation()` is called
        """
        # sanity check market id matches market book
        if market.market_id != market_book.market_id:
            raise MyStrategyException(
                f'expected market id "{market.market_id}" to be the same as market book id "{market_book.market_id}"'
            )

        # check if market has been initialised
        udpt_dir = path.join(self.base_dir, 'strategyupdates', str(self.strategy_id), market_book.market_id)
        if market.market_id not in self.market_handlers:
            makedirs(udpt_dir)
            self.market_handlers[market.market_id] = self.get_market_handler(market, market_book)

        # check market not closed
        mh = self.market_handlers[market.market_id]
        if mh.closed:
            active_logger.warning(f'process_market_book called on market "{market.market_id}" which is closed already')
            return

        # update flags
        mh.update_flag_feature(market_book, self.feature_seconds)
        mh.update_flag_allow(market_book, self.pre_seconds)
        mh.update_flag_cutoff(market_book, self.cutoff_seconds)

        # check that features are to be processed, loop runners
        if mh.flag_feature.current_value:
            # initialise runners if not tracked
            for runner_index, runner_book in enumerate(market_book.runners):
                if runner_book.selection_id not in mh.runner_handlers:
                    # create runner features
                    feature_holder = self.get_featureholder(market, market_book, runner_book, runner_index)
                    # initialise for race
                    for feature in feature_holder.values():
                        feature.race_initializer(runner_book.selection_id, market_book)
                    # create runner handler
                    udt_path = path.join(udpt_dir, 'updates')
                    mh.runner_handlers[runner_book.selection_id] = self.get_runner_handler(
                        mkt=market, mbk=market_book, rbk=runner_book, fh=feature_holder, upth=udt_path, i=runner_index
                    )
            # process runner features
            for runner_index, runner_book in enumerate(market_book.runners):
                self.process_runner_features(market_book, mh, runner_book.selection_id, runner_index)

            # check if trading is to be performed (features flag *should* always be true if allow flag is)
            for runner_index, runner_book in enumerate(market_book.runners):
                rh = mh.runner_handlers[runner_book.selection_id]
                # run trade machine if permitted
                if self.allow_trademachine(market_book, runner_book, mh, rh):
                    self.run_trade_machine(market, market_book, runner_book, runner_index)
                # update order tracker
                rh.trade_tracker.update_order_tracker(market_book.publish_time)

    @timing_register
    def process_closed_market(self, market: Market, market_book: MarketBook) -> None:
        # check market that is closing is in trade trackers
        if market.market_id not in self.market_handlers:
            active_logger.warning(f'market ID "{market.market_id}" closing but not tracked')
            return
        # check market hasn't already been closed
        mh = self.market_handlers[market.market_id]
        if mh.closed:
            active_logger.warning(f'market ID "{market.market_id}" already closed')
            return
        # set marked closed flag
        mh.closed = True
        # loop runners -> trades -> orders
        for selection_id, rh in mh.runner_handlers.items():
            for trade in rh.trade_tracker.trades:
                for order in trade.orders:
                    rh.trade_tracker.log_update(
                        msg_type=MessageTypes.MSG_MARKET_CLOSE,
                        msg_attrs={
                            'runner_status': order.runner_status,
                            'order_id': str(order.id)
                        },
                        dt=market_book.publish_time,
                        order=order,
                    )
        del mh.runner_handlers

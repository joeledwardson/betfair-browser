import json
import uuid
from datetime import datetime, timedelta
from os import path
import os
from typing import Optional, Dict
import logging
import yaml

from betfairlightweight.resources import MarketBook, RunnerBook
from flumine import clients, BaseStrategy
from flumine.markets.market import Market

from .userdata import UserDataLoader, UserDataStreamer
from ..exceptions import MyStrategyException
from ..utils import bettingdb
from .feature import FeatureHolder
from .trademachine import RunnerTradeMachine
from .tradestates import TradeStateTypes
from .messages import MessageTypes
from .tradetracker import TradeTracker
from .runnerhandler import RunnerHandler
from myutils.mytiming import EdgeDetector, timing_register

active_logger = logging.getLogger(__name__)


class BackTestClientNoMin(clients.BacktestClient):
    """flumine back test client with no minimum bet size"""
    @property
    def min_bet_size(self) -> Optional[float]:
        return 0


class MyBaseStrategy(BaseStrategy):
    def check_market_book(self, market: Market, market_book: MarketBook) -> bool:
        """
        return True (tell flumine to run process_market_book()) only executed if market not closed
        """
        if market_book.status != "CLOSED":
            return True


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
        self.closed_markets = []

    def check_market_book(self, market: Market, market_book: MarketBook) -> bool:
        return True

    def process_closed_market(self, market: Market, market_book: MarketBook) -> None:
        market_id = market_book.market_id
        active_logger.info(f'received closed market function for "{market_id}"')
        if market_id in self.closed_markets:
            active_logger.warning(f'market already closed')
        else:
            if market_id not in self.market_paths:
                active_logger.warning(f'market has no stream file')
        self.closed_markets.append(market_id)

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:
        market_id = market_book.market_id
        if market_id not in self.catalogue_paths and market.market_catalogue:
            # get cache path, create dir if not exist
            p = self.db.path_mkt_cat(market_id)
            d, _ = path.split(p)
            os.makedirs(d, exist_ok=True)
            # store catalogue
            self.catalogue_paths[market_id] = p
            active_logger.info(f'writing market id "{market_id}" catalogue to "{p}"')
            with open(p, 'w') as f:
                f.write(market.market_catalogue.json())

        if market_id not in self.market_paths:
            # get cache path, create dir if not exist
            p = self.db.path_mkt_updates(market_id)
            d, _ = path.split(p)
            os.makedirs(d, exist_ok=True)
            # set path var
            self.market_paths[market_id] = p
            active_logger.info(f'new market started recording: "{market_id}" to {p}')

        if market_id in self.closed_markets:
            active_logger.warning(f'received market update for "{market_id}" when market closed')
        else:
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


# TODO - log reason for order validation fail
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
            cutoff_seconds: int,
            pre_seconds: int,
            feature_seconds: int,
            historic: bool,
            db_kwargs: Optional[Dict] = None,
            oc_td: Optional[timedelta] = None,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.strategy_id = uuid.uuid4()
        self.pre_seconds = pre_seconds
        self.cutoff_seconds = cutoff_seconds
        self.feature_seconds = feature_seconds
        self.strategy_name = name
        self.market_handlers: Dict[str, MarketHandler] = dict()
        self._db = bettingdb.BettingDB(**(db_kwargs or {}))
        self.historic = historic
        if historic:
            active_logger.info('client is historic, using recorded user data "UserDataLoader"')
            self._usr_data = UserDataLoader(self._db, oc_td)
        else:
            active_logger.info('client is live, using streaming user data "UserData')
            self._usr_data = UserDataStreamer(self._db, oc_td)

    def strategy_write_info(self, init_kwargs):
        """write strategy information to file"""
        self._db.write_strat_info(
            strategy_id=self.strategy_id,
            type='simulated' if self.historic else 'live',
            name=self.__class__.__name__,
            exec_time=datetime.utcnow(),
            info=init_kwargs,
        )

    def _trade_machine_allow(
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
            sm = rh.trade_machine

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

    def _trade_machine_create(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int) -> RunnerTradeMachine:
        """create trade state machine for a new runner"""
        raise NotImplementedError

    def _trade_machine_run(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int):
        """operate runner trade machine given new market book"""
        raise NotImplementedError

    def _feature_holder_create(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int) -> FeatureHolder:
        """generate feature holder dictionary of feature instance for new runner"""
        raise NotImplementedError

    def _feature_process(self, mb: MarketBook, mh: MarketHandler, selection_id, runner_index):
        """process features for a given runner for new market book"""
        # TODO - write feature values to file?
        def _dump(feature):
            feature.out_cache.clear()
            for sub_ftr in feature.sub_features.items():
                feature.out_cache.clear()
        for feature in mh.runner_handlers[selection_id].features.values():
            feature.process_runner(mb, runner_index)
            _dump(feature)

    def _user_data_process(self, mb: MarketBook, mkt: Market, mh: MarketHandler):
        user_data = self._usr_data.get_user_data(mkt, mb)
        for rh in mh.runner_handlers.values():
            rh.user_data = user_data
            for ftr in rh.features.values():
                ftr.update_user_data(user_data)

    def _runner_handler_create(
            self,
            runner_book: RunnerBook,
            feature_holder: FeatureHolder,
            update_path: str,
            trade_machine: RunnerTradeMachine,
            market_id
    ) -> RunnerHandler:
        """create runner handler instance on new runner"""
        return RunnerHandler(
            selection_id=runner_book.selection_id,
            trade_tracker=TradeTracker(
                selection_id=runner_book.selection_id,
                strategy=self,
                market_id=market_id,
                file_path=update_path
            ),
            trade_machine=trade_machine,
            features=feature_holder
        )

    def _market_handler_create(self, mkt: Market, mbk: MarketBook) -> MarketHandler:
        """create market handler, can be overridden to customise market handler instance with more attributes"""
        return MarketHandler()

    def _market_validate(self, market: Market, market_book: MarketBook):
        """sanity check market id matches market book"""
        if market.market_id != market_book.market_id:
            raise MyStrategyException(
                f'expected market id "{market.market_id}" to be the same as market book id "{market_book.market_id}"'
            )

    @timing_register
    def process_market_book(self, market: Market, market_book: MarketBook):
        """
        get runner feature data for current market with new `market_book` received
        - if first time market is received then `market_initialisation()` is called
        """
        # check if market has been initialised
        udt_path = self._db.path_strat_updates(market.market_id, self.strategy_id)
        if market.market_id not in self.market_handlers:
            d, _ = path.split(udt_path)
            os.makedirs(d)
            self.market_handlers[market.market_id] = self._market_handler_create(market, market_book)

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
                    feature_holder = self._feature_holder_create(market, market_book, runner_book, runner_index)
                    # initialise for race
                    for feature in feature_holder.values():
                        feature.race_initializer(runner_book.selection_id, market_book)
                    # create runner handler
                    tm = self._trade_machine_create(market, market_book, runner_book, runner_index)
                    mh.runner_handlers[runner_book.selection_id] = self._runner_handler_create(
                        runner_book=runner_book,
                        feature_holder=feature_holder,
                        update_path=udt_path,
                        trade_machine=tm,
                        market_id=market.market_id
                    )
            # process user data and runner features
            for runner_index, runner_book in enumerate(market_book.runners):
                self._user_data_process(market_book, market, mh)
                self._feature_process(market_book, mh, runner_book.selection_id, runner_index)

            # check if trading is to be performed (features flag *should* always be true if allow flag is)
            for runner_index, runner_book in enumerate(market_book.runners):
                rh = mh.runner_handlers[runner_book.selection_id]
                # run trade machine if permitted
                if self._trade_machine_allow(market_book, runner_book, mh, rh):
                    self._trade_machine_run(market, market_book, runner_book, runner_index)
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
        active_logger.info(f'market ID "{market.market_id}", closed')
        # set marked closed flag
        mh.closed = True
        # loop runners -> trades -> orders
        for selection_id, rh in mh.runner_handlers.items():
            rh.trade_tracker.log_close(market_book.publish_time)
        del mh.runner_handlers

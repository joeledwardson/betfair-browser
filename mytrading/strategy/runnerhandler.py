from betfairlightweight.resources import MarketBook, RunnerBook
import logging

from ..process import get_best_price
from .feature import FeatureHolder
from mytrading.strategy.messages import MessageTypes
from .tradetracker import TradeTracker

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class RunnerHandler:
    def __init__(
            self,
            selection_id: int,
            trade_tracker: TradeTracker,
            trade_machine,
            features: FeatureHolder
    ):
        self.selection_id = selection_id
        self.features: FeatureHolder = features
        self.trade_tracker = trade_tracker
        self.trade_machine = trade_machine
        self.user_data = None

    def rst_trade(self):
        """process a complete trade by forcing trade machine back to initial state, clearing active order and active
        trade"""

        # clear existing states from state machine
        self.trade_machine.flush()

        # reset to starting states
        self.trade_machine.force_change([self.trade_machine.initial_state_key])

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
        self.trade_machine.flush()
        self.trade_machine.force_change(hedge_states)
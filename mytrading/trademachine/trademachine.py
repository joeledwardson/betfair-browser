from .tradestates import TradeStateTypes
from mytrading.tradetracker.messages import MessageTypes
from betfairlightweight.resources import MarketBook
from mytrading.tradetracker.tradetracker import TradeTracker
from myutils import statemachine as stm


import logging
from typing import Dict
from enum import Enum

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class RunnerStateMachine(stm.StateMachine):
    """
    implement state machine for runners, logging state changes with runner ID
    """
    def __init__(self, states: Dict[Enum, stm.State], initial_state: Enum, selection_id: int):
        super().__init__(states, initial_state)
        self.selection_id = selection_id

    def process_state_change(
            self,
            old_state,
            new_state,
            market_book: MarketBook,
            trade_tracker: TradeTracker,
            **kwargs):
        trade_tracker.log_update(
            msg_type=MessageTypes.STATE_CHANGE,
            msg_attrs={
                'old_state': str(old_state),
                'new_state': str(new_state)
            },
            dt=market_book.publish_time,
        )


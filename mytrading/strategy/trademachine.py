from .messages import MessageTypes
from myutils import statemachine as stm
from flumine.markets.market import Market
import logging
from typing import Dict
from enum import Enum

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class RunnerTradeMachine(stm.StateMachine):
    """
    implement state machine for runners, logging state changes with runner ID
    """

    # override state types
    states: Dict

    def __init__(self, states: Dict, initial_state: Enum, selection_id: int):
        super().__init__(states, initial_state)
        self.selection_id = selection_id

    def process_state_change(
            self, old_state: Enum, new_state: Enum, market: Market, runner_index: int, runner_handler
    ):
        # if state specifies that on entering dont print update, exit
        if not self.states[new_state].print_change_message:
            return

        runner_handler.trade_tracker.log_update(
            msg_type=MessageTypes.MSG_STATE_CHANGE,
            msg_attrs={
                'old_state': old_state.name,
                'new_state': new_state.name
            },
            dt=market.market_book.publish_time,
        )


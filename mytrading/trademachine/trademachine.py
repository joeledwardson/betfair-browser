from mytrading.trademachine.tradestates import TradeStates
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

    def process_state_change(self, old_state, new_state):
        active_logger.info(f'runner "{self.selection_id}" has changed from state "{old_state}" to "{new_state}"')
        if new_state == TradeStates.PENDING:
            my_debug_breakpoint = True



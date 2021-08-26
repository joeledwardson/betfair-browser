import queue
import logging
from enum import Enum
from typing import Dict, List
from .exceptions import StateMachineException

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class State:
    def enter(self, **inputs):
        pass

    def run(self, **inputs):
        raise NotImplementedError


class StateMachine:
    def __init__(self, states: Dict[Enum, State], initial_state: Enum):
        self.states: Dict[Enum, State] = states
        self.current_state_key: Enum = initial_state
        self.previous_state_key: Enum = initial_state
        self.initial_state_key: Enum = initial_state
        self.is_state_change: bool = True
        self.state_queue = queue.Queue()

    def flush(self):
        """
        clear state queue
        """
        self.state_queue.queue.clear()

    def force_change(self, new_states: List[Enum]):
        """
        updating current state to first in queue and forcibly add a list of new states to queue
        """
        for state_key in new_states:
            self.state_queue.put(state_key)
        self.current_state_key = self.state_queue.get()
        self.is_state_change = True

    def run(self, **kwargs):
        """
        run state machine with `kwargs` dictionary repeatedly until no state change is detected
        """

        while 1:

            if self.is_state_change:
                self.states[self.current_state_key].enter(**kwargs)

            self.previous_state_key = self.current_state_key

            ret = self.states[self.current_state_key].run(**kwargs)

            if type(ret) == list:
                # list returned, add all to queue
                for s in ret:
                    self.state_queue.put(s)
                self.current_state_key = self.state_queue.get()
            elif ret is None or ret is False or ret == self.current_state_key:
                # no value returned or same state returned, same state
                pass
            elif isinstance(ret, Enum):
                # True means go to next state, None means use existing, otherwise single state value has been
                # returned so add to queue
                self.state_queue.put(ret)
                self.current_state_key = self.state_queue.get()
            elif ret is True:
                # returned value implies state change (True, list of states, or single new state)
                if not self.state_queue.qsize():
                    # state has returned true when nothing in queue! (this shouldn't happen)
                    raise StateMachineException('state machine queue has no size')
                # get next state from queue
                self.current_state_key = self.state_queue.get()
            else:
                # unrecognized return type
                raise StateMachineException(f'return value "{ret}" in state machine not recognised')

            self.is_state_change = self.previous_state_key != self.current_state_key
            if self.is_state_change:
                # new state is different to current, process change and repeat loop
                self.process_state_change(self.previous_state_key, self.current_state_key, **kwargs)
            else:
                # exit loop if no state change
                break

    def process_state_change(self, old_state, new_state, **kwargs):
        pass


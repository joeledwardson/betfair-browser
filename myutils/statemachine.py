import queue
import logging
from enum import Enum
from typing import Dict

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class State:
    def enter(self):
        pass

    def run(self, **inputs):
        assert 0, "run not implemented"


class StateMachine:
    def __init__(self, states: Dict[Enum, State], initial_state: Enum):
        self.states: Dict[Enum, State] = states
        self.current_state_key: Enum = initial_state
        self.previous_state_key: Enum = initial_state
        self.is_state_change: bool = True
        self.state_queue = queue.Queue()

    # Template method:
    def run(self, **kwargs):

        while 1:

            if self.selection_id == 28400302:
                my_debug_breakpoint=True

            if self.is_state_change:
                self.states[self.current_state_key].enter()

            self.previous_state_key = self.current_state_key

            ret = self.states[self.current_state_key].run(**kwargs)

            if type(ret) == list:
                # list returned, add all to queue
                for s in ret:
                    self.state_queue.put(s)

            elif ret is not True and ret is not None:
                # True means go to next state, None means use existing, otherwise single state value has been
                # returned so add to queue
                self.state_queue.put(ret)

            if ret is None or ret == self.current_state_key:
                # no value returned or same state returned, same state
                self.current_state_key = self.previous_state_key

            else:
                # returned value implies state change (True, list of states, or single new state)
                if not self.state_queue.qsize():
                    # state has returned true when nothing in queue! (this shouldn't happen)
                    active_logger.warning('queue has no size')
                    self.current_state_key = self.previous_state_key

                else:
                    # get next state from queue
                    self.current_state_key = self.state_queue.get()

            self.is_state_change = self.previous_state_key != self.current_state_key
            if self.is_state_change:
                # new state is different to current, process change and repeat loop
                self.process_state_change(self.previous_state_key, self.current_state_key)

            else:
                # exit loop if no state change
                break

    def process_state_change(self, old_state, new_state):
        pass


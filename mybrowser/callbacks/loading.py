from .globals import IORegister

from os import path
import dash
from dash.dependencies import Output, Input, State
from typing import Dict, List
import logging
from ..data import DashData
from ..app import app, dash_data as dd
from .globals import IORegister
from myutils.mydash import intermediate, context
import itertools


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class LoadTracker:
    def __init__(self):
        self.input_pairs = {
            x.component_id: x.component_property
            for x in IORegister.inputs_reg
        }
        self.mid_pairs = {
            x.component_id: x.component_property
            for x in IORegister.outs_reg
        }

        self.is_loading = False
        self.is_complete = False

    def reset(self):
        self.is_loading = False
        self.is_complete = False

    def process_input(self, cmp_id) -> bool:
        if cmp_id in self.input_pairs:
            if self.is_complete:
                active_logger.warning(f'input ID "{cmp_id}" received after loading complete, resetting...')
                self.reset()
                return False
            else:
                self.is_loading = True
                return True
        elif cmp_id in self.mid_pairs:
            if not self.is_loading:
                active_logger.warning(f'intermediary ID "{cmp_id}" received before loading started...')
                self.is_complete = True
                return False
            else:
                return True


load_tracker = LoadTracker()
inputs = [
    Input(k, v)
    for k, v in (
            load_tracker.mid_pairs | load_tracker.input_pairs
    ).items()
]


@app.callback(
    output=[
        Output('loading-bar', 'children'),
    ],
    inputs=inputs,
)
def loading(*args):
    cmp_id = context.triggered_id()
    active_logger.info(f'loading callback triggered from "{cmp_id}"')
    b = load_tracker.process_input(cmp_id)
    s = 'loading' if b else ''
    return [s]

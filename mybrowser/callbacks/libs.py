import dash
from dash.dependencies import Output, Input, State
from datetime import datetime
import sys
import importlib
import logging
from myutils.mydash import intermediate, context
from ..app import app
from .globals import IORegister

active_logger = logging.getLogger(__name__)
counter = intermediate.Intermediary()

mid = Output('intermediary-libs', 'children')
inputs = [
    Input('button-libs', 'n_clicks'),
    Input('modal-close-libs', 'n_clicks')
]
IORegister.register_inputs(inputs)
IORegister.register_mid(mid)


@app.callback(
    output=[
        mid,
        Output('modal-libs', 'is_open'),
        Output('loading-out-header', 'children')
    ],
    inputs=inputs,
    state=[State('modal-libs', 'is_open')]
)
def callack_libs(n1, n2, is_open):
    """
    when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
    """
    if context.triggered_id() == 'button-libs':
        for k in list(sys.modules.keys()):
            if 'mytrading' in k or 'myutils' in k:
                importlib.reload(sys.modules[k])
                active_logger.debug(f'reloaded library {k}')
        active_logger.info('libraries reloaded')
        return counter.next(), True, ''

    else:
        return counter.next(), False, ''




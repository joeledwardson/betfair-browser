from dash.dependencies import Output, Input, State
import sys
import importlib
import logging
from myutils.mydash import intermediate, context
from ..app import app, dash_data

active_logger = logging.getLogger(__name__)
counter = intermediate.Intermediary()


@app.callback(
    output=[
        Output('intermediary-libs', 'children'),
        Output('modal-libs', 'is_open'),
        Output('loading-out-header', 'children')
    ],
    inputs=[
        Input('button-libs', 'n_clicks'),
        Input('modal-close-libs', 'n_clicks')
    ],
    state=[
        State('modal-libs', 'is_open')
    ]
)
def callback_libs(n1, n2, is_open):
    """
    when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
    """
    if context.triggered_id() == 'button-libs':
        dash_data.reload_modules()
        return counter.next(), True, ''

    else:
        return counter.next(), False, ''




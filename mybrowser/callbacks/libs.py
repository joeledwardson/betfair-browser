import dash
from dash.dependencies import Output, Input
from datetime import datetime
import sys
import importlib
import logging
from myutils.mydash import intermediate
from ..app import app

active_logger = logging.getLogger(__name__)
counter = intermediate.Intermediary()


@app.callback(
    output=Output('intermediary-libs', 'children'),
    inputs=[
        Input('button-libs', 'n_clicks'),
    ],
)
def update_files_table(libs_n_clicks):
    """
    when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
    """
    for k in list(sys.modules.keys()):
        if 'mytrading' in k or 'myutils' in k:
            importlib.reload(sys.modules[k])
    active_logger.info('libraries reloaded')
    return counter.next()

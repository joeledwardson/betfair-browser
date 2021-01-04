import dash
from dash.dependencies import Output, Input
from datetime import datetime
import sys
import importlib
from ..logger import cb_logger
from ..intermediary import Intermediary

counter = Intermediary()


def libs_callback(app: dash.Dash):
    """
    when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
    """
    @app.callback(
        output=Output('intermediary-libs', 'children'),
        inputs=[
            Input('button-libs', 'n_clicks'),
        ],
    )
    def update_files_table(libs_n_clicks):
        for k in list(sys.modules.keys()):
            if 'mytrading' in k or 'myutils' in k:
                importlib.reload(sys.modules[k])
        cb_logger.info('libraries reloaded')
        return counter.next()

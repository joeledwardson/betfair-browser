import dash
from dash.dependencies import Output, Input
from datetime import datetime
import sys
import importlib


def libs_callback(app: dash.Dash):
    """
    when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
    """
    @app.callback(
        output=Output('info-libs', 'children'),
        inputs=[
            Input('button-libs', 'n_clicks'),
        ],
    )
    def update_files_table(libs_n_clicks):
        for k in list(sys.modules.keys()):
            if 'mytrading' in k or 'myutils' in k:
                importlib.reload(sys.modules[k])
        return f'libraries reloaded at: {datetime.now()}'

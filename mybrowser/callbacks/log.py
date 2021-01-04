import dash
from dash.dependencies import Output, Input, State
import dash_html_components as html
from ..data import DashData
from ..logger import log_q

log_elements = []


def log_callback(app: dash.Dash):
    @app.callback(
        output=Output('logger-box', 'children'),
        inputs=[
            Input('intermediary-market', 'children'),
            Input('intermediary-featureconfigs', 'children'),
            Input('intermediary-figure', 'children'),
            Input('intermediary-libs', 'children'),
            Input('intermediary-orders', 'children'),
            Input('intermediary-files', 'children')
        ],
    )
    def log_update(*args, **kwargs):
        # update log list, add to bottom of list as display is reversed
        while not log_q.empty():
            log_elements.insert(0, html.P(
                log_q.get(),
                style={
                    'margin': 0,
                    'white-space': 'pre'
                }
            ))
        return log_elements

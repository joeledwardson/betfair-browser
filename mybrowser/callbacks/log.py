import dash
from dash.dependencies import Output, Input, State
import dash_html_components as html
from ..data import DashData
from .. import log_q
from ..app import app
from .globals import IORegister


log_elements = []


@app.callback(
    output=Output('logger-box', 'children'),
    inputs=[
        Input(x.component_id, x.component_property)
        for x in IORegister.outs_reg
    ] + [
        Input('interval-component', 'n_intervals')
    ]
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

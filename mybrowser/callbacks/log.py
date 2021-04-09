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
        log_item = log_q.get()
        log_elements.insert(0, html.P(
            log_item['txt'],
            style={
                'margin': 0,
                # 'white-space': 'pre',
                'background-color': 'yellow' if log_item['record'].levelname == 'WARNING' else None,
            }
        ))
    return log_elements


@app.callback(
    Output("modal-logs", "is_open"),
    [Input("button-log", "n_clicks"), Input("modal-close-log", "n_clicks")],
    [State("modal-logs", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open
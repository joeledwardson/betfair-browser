from dash.dependencies import Output, Input, State
import dash_html_components as html

from .. import log_q
from ..app import app
from ..intermeds import INTERMEDIARIES


log_elements = []

inputs = [Input(x, 'children') for x in INTERMEDIARIES]
inputs += [Input('interval-component', 'n_intervals')]


@app.callback(
    output=Output('logger-box', 'children'),
    inputs=inputs
)
def log_update(*args):
    # update log list, add to bottom of list as display is reversed
    while not log_q.empty():
        log_item = log_q.get()
        log_elements.insert(0, html.P(
            log_item['txt'],
            style={
                'margin': 0,
                # TODO - add colours for error/critical as well
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
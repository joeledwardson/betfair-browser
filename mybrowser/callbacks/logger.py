from dash.dependencies import Output, Input, State
import dash_html_components as html

from .. import log_q
from ..session import Session
from ..layouts import INTERMEDIARIES
from myutils.mydash import context

# mapping of log levels to bootstrap background colors
LEVEL_COLORS = {
    'DEBUG': 'bg-white',
    'INFO': 'bg-light',
    'WARNING': 'bg-warning',
    'ERROR': 'bg-danger',
    'CRITICAL': 'bg-danger'
}


def cb_logs(app, shn: Session):
    @app.callback(
        output=[
            Output('logger-box', 'children'),
            Output('msg-alert-box', 'hidden'),
            Output('log-warns', 'children')
        ],
        inputs=[
            Input(x, 'children') for x in INTERMEDIARIES
        ] + [
            Input('interval-component', 'n_intervals'),
            Input("modal-close-log", "n_clicks")
        ]
    )
    def log_update(*args):

        # update log list, add to bottom of list as display is reversed
        while not log_q.empty():
            log_item = log_q.get()
            lvl = log_item['record'].levelname
            if lvl in ['WARNING', 'ERROR', 'CRITICAL']:
                shn.log_nwarn += 1
            shn.log_elements.insert(0, html.P(
                log_item['txt'],
                className='m-0 ' + LEVEL_COLORS.get(lvl, '')
            ))

        if context.triggered_id() == 'modal-close-log':
            shn.log_nwarn = 0

        if shn.log_nwarn > 0:
            hide_warn = False
        else:
            hide_warn = True

        return shn.log_elements, hide_warn, str(shn.log_nwarn)

    @app.callback(
        output=Output("modal-logs", "is_open"),
        inputs=[
            Input("button-log", "n_clicks"),
            Input("modal-close-log", "n_clicks")
        ]
    )
    def toggle_modal(n1, n2):
        if context.triggered_id() == 'button-log':
            return True
        else:
            return False



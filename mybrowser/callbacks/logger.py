from dash.dependencies import Output, Input, State
import dash_html_components as html
import dash_bootstrap_components as dbc
from typing import List, Dict

import dash
from myutils import dashutils
# from .. import log_q
from ..session import Session, Notification
from ..layouts import INTERMEDIARIES

# mapping of log levels to bootstrap background colors
LEVEL_COLORS = {
    'DEBUG': 'bg-white',
    'INFO': 'bg-light',
    'WARNING': 'bg-warning',
    'ERROR': 'bg-danger',
    'CRITICAL': 'bg-danger'
}
MAX_ELEMENTS = 1000
STORES = [
    'notifications-runners',
    'notifications-market',
    'notifications-strategy-reload',
    'notifications-configs',
    'notifications-libs',
    'notifications-strategy'
]
def cb_logs(app, shn: Session):
    @app.callback(
        output=[
            # Output('logger-box', 'children'),
            # Output('msg-alert-box', 'hidden'),
            # Output('log-warns', 'children'),
            Output('toast-holder', 'children')
        ],
        inputs=[
            Input(s, 'data') for s in STORES
        ] + [
            Input("url", "pathname")
        ],
        state=[
            State('toast-holder', 'children'),
        ]
    )
    def log_update(*args):
        toasts = args[-1] or []
        pathname = args[-2]

        # remove past toasts after duration
        toasts = [t for t in toasts if t['props']['children']['props']['is_open']]

        for e in dashutils.all_triggered_ids():
            if e in STORES:
                idx = STORES.index(e)
                new_notifications: List[Notification] = args[idx] or []
                toasts += [
                    html.Div(dbc.Toast(
                        [html.P(p['msg_content'], className="mb-0")],
                        header=p['msg_header'],
                        icon=p['msg_type'],
                        duration=5000,
                        is_open=True,
                        dismissable=True,
                    ))
                    for p in new_notifications
                ]

        # update log list, add to bottom of list as display is reversed
        # while not log_q.empty():
        #     log_item = log_q.get()
        #     lvl = log_item['record'].levelname
        #     if lvl in ['WARNING', 'ERROR', 'CRITICAL']:
        #         shn.log_nwarn += 1
        #     shn.log_elements.insert(0, html.P(
        #         log_item['txt'],
        #         className='m-0 ' + LEVEL_COLORS.get(lvl, '')
        #     ))
        #     shn.log_elements = shn.log_elements[:MAX_ELEMENTS]
        #
        # if pathname == "/logs":
        #     shn.log_nwarn = 0
        #     hide_warn = True
        # else:
        #     if shn.log_nwarn > 0:
        #         hide_warn = False
        #     else:
        #         hide_warn = True

        # toasts = list() if not toasts else toasts
        # while shn.notif_exist():
        #     new_notif = shn.notif_pop()
        #     toasts.append(
        #         html.Div(dbc.Toast(
        #             [html.P(new_notif.msg_content, className="mb-0")],
        #             header=new_notif.msg_header,
        #             icon=new_notif.msg_type.value,
        #             duration=5000,
        #             is_open=True,
        #             dismissable=True,
        #         ))
        #     )

        return [
            # shn.log_elements,
            # hide_warn,
            # str(shn.log_nwarn),
            toasts
        ]

    @app.callback(
        output=[
            Output('test-div', 'children')
        ],
        inputs=[Input('toast-holder', 'children')]
    )
    def log_update(toasts):
        if(type(toasts) == list):
            print(f'*****number of notifications present: {len(toasts)}')
        return ['']
from dash.dependencies import Output, Input, State
import logging

import myutils.mydash
from ..session import Session

active_logger = logging.getLogger(__name__)
counter = myutils.mydash.Intermediary()


def cb_libs(app, shn: Session):
    @app.callback(
        output=[
            Output('intermediary-libs', 'children'),
            Output('modal-libs', 'is_open'),
            Output('loading-out-header', 'children')
        ],
        inputs=[
            Input('button-libs', 'n_clicks'),
            Input('modal-close-libs', 'n_clicks')
        ]
    )
    def callback_libs(n1, n2):
        """
        when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
        """
        if myutils.mydash.triggered_id() == 'button-libs':
            shn.rl_mods()
            return counter.next(), True, ''

        else:
            return counter.next(), False, ''




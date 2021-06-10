from dash.dependencies import Output, Input, State
import logging

import myutils.mydash
from ..session import Session, Notification as Notif, NotificationType as NType

active_logger = logging.getLogger(__name__)
counter = myutils.mydash.Intermediary()


def cb_libs(app, shn: Session):
    @app.callback(
        output=[
            Output('intermediary-libs', 'children'),
            Output('loading-out-libs', 'children')
        ],
        inputs=[
            Input('button-libs', 'n_clicks')
        ]
    )
    def callback_libs(n1):
        """
        when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
        """
        if myutils.mydash.triggered_id() == 'button-libs':
            n = shn.rl_mods()
            shn.notif_post(Notif(NType.INFO, 'Libraries', f'{n} modules reloaded'))

        return counter.next(), ''




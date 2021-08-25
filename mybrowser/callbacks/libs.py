from dash.dependencies import Output, Input, State
import logging

import myutils.dashutils
from ..session import Session,post_notification
active_logger = logging.getLogger(__name__)
counter = myutils.dashutils.Intermediary()


def cb_libs(app, shn: Session):
    @app.callback(
        output=[
            Output('intermediary-libs', 'children'),
            Output('loading-out-libs', 'children'),
            Output('notifications-libs', 'data')
        ],
        inputs=[
            Input('button-libs', 'n_clicks')
        ]
    )
    def callback_libs(n1):
        """
        when reload libraries button pressed, dynamically update references to `mytrading` and `myutils`
        """
        notifs = []
        if myutils.dashutils.triggered_id() == 'button-libs':
            n = shn.rl_mods()
            post_notification('info', 'Libraries', f'{n} modules reloaded')

        return [
            counter.next(),
            '',
            notifs
        ]




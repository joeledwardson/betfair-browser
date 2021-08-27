from dash.dependencies import Output, Input, State
import myutils.dashutils
from ..session import Session,post_notification


def cb_libs(app, shn: Session):
    @app.callback(
        output=[
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
            post_notification(notifs, 'info', 'Libraries', f'{n} modules reloaded')

        return [
            '',
            notifs
        ]




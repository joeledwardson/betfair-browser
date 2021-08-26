from dash.dependencies import Output, Input, State
import logging
import traceback

import myutils.dashutils
from ..session import Session, post_notification
from ..exceptions import SessionException

counter = myutils.dashutils.Intermediary()
active_logger = logging.getLogger(__name__)


def cb_configs(app, shn: Session):
    @app.callback(
        output=[
            Output('input-feature-config', 'options'),
            Output('input-plot-config', 'options'),
            Output('intermediary-featureconfigs', 'children'),
            Output('notifications-configs', 'data')
        ],
        inputs=[
            Input('button-feature-config', 'n_clicks'),
        ]
    )
    def update_files_table(n_clicks):
        notifs = []
        try:
            shn.ftr_update()
        except SessionException as e:
            active_logger.warning(f'error getting feature configs: {e}\n{traceback.format_exc()}')
            post_notification(notifs, 'warning', 'Feature Configs', 'failed getting feature configs')

        feature_options = [{
            'label': v,
            'value': v,
        } for v in shn.feature_configs.keys()]
        plot_options = [{
            'label': v,
            'value': v,
        } for v in shn.plot_configs.keys()]

        post_notification(notifs, 'info', 'Feature Configs', f'{len(shn.feature_configs)} feature configs loaded')
        post_notification(notifs, 'info', 'Plot Configs', f'{len(shn.plot_configs)} plot configs loaded')
        return [
            feature_options,
            plot_options,
            counter.next(),
            notifs
        ]

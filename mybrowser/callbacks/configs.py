from dash.dependencies import Output, Input, State
import logging
import traceback

import myutils.dashutils
from ..session import Session, Notification as Notif, NotificationType as NType
from ..exceptions import SessionException

counter = myutils.dashutils.Intermediary()
active_logger = logging.getLogger(__name__)


def cb_configs(app, shn: Session):
    @app.callback(
        output=[
            Output('input-feature-config', 'options'),
            Output('input-plot-config', 'options'),
            Output('intermediary-featureconfigs', 'children')
        ],
        inputs=[
            Input('button-feature-config', 'n_clicks'),
        ]
    )
    def update_files_table(n_clicks):
        try:
            shn.ftr_update()
        except SessionException as e:
            active_logger.warning(f'error getting feature configs: {e}\n{traceback.format_exc()}')
            shn.notif_post(Notif(
                msg_type=NType.WARNING, msg_header='Feature Configs', msg_content='failed getting feature configs'
            ))

        feature_options = [{
            'label': v,
            'value': v,
        } for v in shn.ftr_fcfgs.keys()]
        plot_options = [{
            'label': v,
            'value': v,
        } for v in shn.ftr_pcfgs.keys()]

        shn.notif_post(Notif(
            msg_type=NType.INFO,
            msg_header='Feature Configs',
            msg_content=f'{len(shn.ftr_fcfgs)} feature configs loaded'
        ))
        shn.notif_post(Notif(
            msg_type=NType.INFO,
            msg_header='Plot Configs',
            msg_content=f'{len(shn.ftr_pcfgs)} plot configs loaded'
        ))
        return [
            feature_options,
            plot_options,
            counter.next()
        ]

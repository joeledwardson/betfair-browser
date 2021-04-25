from dash.dependencies import Output, Input, State
import logging
import traceback

from myutils import mydash as myd
from ..session import Session, SessionException

counter = myd.Intermediary()
active_logger = logging.getLogger(__name__)


def cb_configs(app, shn: Session):
    @app.callback(
        output=[
            Output('input-feature-config', 'options'),
            Output('input-plot-config', 'options'),
            Output('intermediary-featureconfigs', 'children'),
        ],
        inputs=Input('button-feature-config', 'n_clicks'),
    )
    def update_files_table(n_clicks):

        try:
            shn.ftr_update()
        except SessionException as e:
            active_logger.warning(f'error getting feature configs: {e}\n{traceback.format_exc()}')

        feature_options = [{
            'label': v,
            'value': v,
        } for v in shn.ftr_fcfgs.keys()]
        plot_options = [{
            'label': v,
            'value': v,
        } for v in shn.ftr_pcfgs.keys()]

        return [
            feature_options,
            plot_options,
            counter.next(),
        ]

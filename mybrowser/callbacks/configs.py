from dash.dependencies import Output, Input, State
import logging


from myutils.mydash import intermediate
from ..session import Session

counter = intermediate.Intermediary()
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

        shn.ftr_load()

        feature_options = [{
            'label': v,
            'value': v,
        } for v in shn.feature_configs.keys()]
        plot_options = [{
            'label': v,
            'value': v,
        } for v in shn.plot_configs.keys()]

        return [
            feature_options,
            plot_options,
            counter.next(),
        ]

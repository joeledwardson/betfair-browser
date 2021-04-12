from dash.dependencies import Output, Input, State
import logging


from myutils.mydash import intermediate
from ..app import app, dash_data as dd


counter = intermediate.Intermediary()
active_logger = logging.getLogger(__name__)


@app.callback(
    output=[
        Output('input-feature-config', 'options'),
        Output('input-plot-config', 'options'),
        Output('intermediary-featureconfigs', 'children'),
    ],
    inputs=Input('button-feature-config', 'n_clicks'),
)
def update_files_table(n_clicks):

    dd.load_ftr_configs()

    feature_options = [{
        'label': v,
        'value': v,
    } for v in dd.feature_configs.keys()]
    plot_options = [{
        'label': v,
        'value': v,
    } for v in dd.plot_configs.keys()]

    return [
        feature_options,
        plot_options,
        counter.next(),
    ]

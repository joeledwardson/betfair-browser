from os import path
from dash.dependencies import Output, Input, State
from typing import Dict, List
import logging

from ..app import app, dash_data as dd
from ..config import config

from myutils.mydash import intermediate
from myutils import mypath
from myutils import jsonfile

counter = intermediate.Intermediary()
active_logger = logging.getLogger(__name__)


def get_configs(config_dir: str) -> Dict:
    """
    get dictionary of configuration file name (without ext) to dict from dir

    Parameters
    ----------
    info_strings :
    config_dir :

    Returns
    -------

    """

    # check directory is set
    if type(config_dir) is not str:
        active_logger.error('directory not set')
        return dict()

    # check actually exists
    if not path.exists(config_dir):
        active_logger.error(f'directory does not exist!')
        return dict()

    # dict of configs to return
    configs = dict()

    # get files in directory
    _, _, files = mypath.walk_first(config_dir)

    # loop files
    for file_name in files:

        # get file path and name without ext
        file_path = path.join(config_dir, file_name)
        name, _ = path.splitext(file_name)

        # read configuration from dictionary
        cfg = jsonfile.read_file_data(file_path)

        # check config successfully parsed
        if cfg is not None:
            configs[name] = cfg

    active_logger.info(f'{len(configs)} valid configuration files found from {len(files)} files')
    active_logger.info(f'feature configs: {list(configs.keys())}')
    return configs


@app.callback(
    output=[
        Output('input-feature-config', 'options'),
        Output('input-plot-config', 'options'),
        Output('intermediary-featureconfigs', 'children'),
    ],
    inputs=Input('button-feature-config', 'n_clicks'),
)
def update_files_table(n_clicks):

    # get feature configs
    feature_dir = path.abspath(config['CONFIG_PATHS']['feature'])
    active_logger.info(f'getting feature configurations from:\n-> {feature_dir}"')
    dd.feature_configs = get_configs(feature_dir)

    # get plot configurations
    plot_dir = path.abspath(config['CONFIG_PATHS']['feature'])
    active_logger.info(f'getting plot configurations from:\n-> {plot_dir}"')
    dd.plot_configs = get_configs(plot_dir)

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

from os import path
import dash
from dash.dependencies import Output, Input, State
from typing import Dict, List
import logging
from ..data import DashData
from ..text import html_lines
from ..logger import cb_logger
from ..intermediary import Intermediary

from myutils import mypath
from myutils import jsonfile

counter = Intermediary()


def get_configs(config_dir: str, config_type: str) -> Dict:
    """
    get dictionary of configuration file name (without ext) to dict from dir

    Parameters
    ----------
    info_strings :
    config_dir :

    Returns
    -------

    """

    cb_logger.info(f'getting {config_type} configurations from "{config_dir}"')

    # check directory is set
    if type(config_dir) is not str:
        cb_logger.warning('directory not set')
        return dict()

    # check actually exists
    if not path.exists(config_dir):
        cb_logger.warning(f'directory does not exist!')
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

    cb_logger.info(f'{len(configs)} valid configuration files found from {len(files)} files')
    cb_logger.info(f'feature configs: {list(configs.keys())}')
    return configs


def feature_configs_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('input-feature-config', 'options'),
            Output('input-plot-config', 'options'),
            Output('intermediary-featureconfigs', 'children')
        ],
        inputs=[
            Input('button-feature-config', 'n_clicks'),
        ],
    )
    def update_files_table(n_clicks):

        # get feature configs directory from data object
        dd.feature_configs = get_configs(dd.feature_configs_dir, 'features')
        dd.plot_configs = get_configs(dd.plot_configs_dir, 'plot')

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

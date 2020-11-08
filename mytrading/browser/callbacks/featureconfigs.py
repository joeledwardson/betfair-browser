from os import path
import dash
from dash.dependencies import Output, Input, State
from typing import Dict, List
import logging

from mytrading.browser.data import DashData
from mytrading.browser.tables.runners import get_runner_id
from mytrading.browser.text import html_lines
from mytrading.utils.storage import EXT_ORDER_RESULT
from mytrading.visual.profits import read_profit_table, process_profit_table
from myutils.mydash.context import triggered_id
from myutils.mypath import walk_first
from myutils.jsonfile import read_file_data

active_logger = logging.getLogger(__name__)


def get_configs(config_dir: str, info_strings: List[str]) -> Dict:
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
        info_strings.append('directory not set')
        return dict()

    # check actually exists
    if not path.exists(config_dir):
        info_strings.append('directory does not exist!')
        return dict()

    # dict of configs to return
    configs = dict()

    # get files in directory
    _, _, files = walk_first(config_dir)

    # loop files
    for file_name in files:

        # get file path and name without ext
        file_path = path.join(config_dir, file_name)
        name, _ = path.splitext(file_name)

        # read configuration from dictionary
        cfg = read_file_data(file_path)

        # check config successfully parsed
        if cfg is not None:
            configs[name] = cfg

    info_strings.append(f'{len(configs)} valid feature configuration files found from {len(files)} files')
    return configs


def feature_configs_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('input-feature-config', 'options'),
            Output('input-plot-config', 'options'),
            Output('infobox-feature-config', 'children')
        ],
        inputs=[
            Input('button-feature-config', 'n_clicks'),
        ],
    )
    def update_files_table(n_clicks):

        # get feature configs directory from data object
        feature_dir = dd.feature_configs_dir
        plot_dir = dd.plot_configs_dir

        info_strings = list()
        info_strings.append(f'Feature configurations dir: "{feature_dir}"')
        info_strings.append(f'Plot configurations dir: "{plot_dir}"')

        dd.feature_configs = get_configs(feature_dir, info_strings)
        dd.plot_configs = get_configs(plot_dir, info_strings)

        active_logger.info(f'feature configs: {list(dd.feature_configs.keys())}')
        active_logger.info(f'plot configs: {list(dd.plot_configs.keys())}')

        feature_options = [{
            'label': v,
            'value': v,
        } for v in dd.feature_configs.values()]
        plot_options = [{
            'label': v,
            'value': v,
        } for v in dd.plot_configs.values()]

        return [
            feature_options,
            plot_options,
            html_lines(info_strings),
        ]

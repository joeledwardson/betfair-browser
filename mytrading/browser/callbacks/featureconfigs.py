from os import path

import dash
from dash.dependencies import Output, Input, State

from mytrading.browser.data import DashData
from mytrading.browser.tables.runners import get_runner_id
from mytrading.browser.text import html_lines
from mytrading.utils.storage import EXT_ORDER_RESULT
from mytrading.visual.profits import read_profit_table, process_profit_table
from myutils.mydash.context import triggered_id
from myutils.mypath import walk_first
from myutils.jsonfile import read_file_data


def feature_configs_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('input-feature-config', 'options'),
            Output('infobox-feature-config', 'children')
        ],
        inputs=[
            Input('button-feature-config', 'n_clicks'),
        ],
    )
    def update_files_table(n_clicks):

        # get feature configs directory from data object
        config_dir = dd.feature_configs_dir

        info_strings = list()
        info_strings.append(f'Feature configurations dir: "{config_dir}"')

        # options to output to dropdown
        options = []

        # clear feature configurations
        dd.feature_configs = dict()

        # check directory is set
        if type(config_dir) is str:

            # check actually exists
            if path.exists(config_dir):

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
                        dd.feature_configs[name] = cfg
                        options.append({
                            'label': name,
                            'value': name
                        })

                info_strings.append(f'{len(options)} valid feature configuration files found from {len(files)} files')

            else:
                info_strings.append('directory does not exist!')

        else:
            info_strings.append('directory not set')

        return options, html_lines(info_strings)
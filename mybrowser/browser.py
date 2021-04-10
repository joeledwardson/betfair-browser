from __future__ import annotations
import dash
import dash_renderer
from typing import Optional, List
from .app import app, dash_data
from . import callbacks
from .layout import get_layout
from datetime import timedelta
import logging
import sys
import dash_bootstrap_components as dbc

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def run_browser(
        debug: bool,
        default_chart_offset: timedelta,
        input_dir: str,
        feature_config_default: str,
        plot_config_default: Optional[str] = None,
        feature_configs_dir: Optional[str] = None,
        plot_configs_dir: Optional[str] = None,
        start_dir: Optional[str] = None,
        feature_config_initial: Optional[str] = None,
        plot_config_initial: Optional[str] = None,
        external_stylesheets: Optional[List[str]] = None,
):
    """
    run dash app mybrowser - input_dir specifies input directory for entry point for mybrowser but also expected root for:
    - "historical" dir
    - "recorded" dir
    """
    if sys.version_info < (3, 9):
        raise Exception('Python version needs to be 3.9 or higher!')

    # dash_data.input_dir=input_dir
    # dash_data.feature_configs_dir=feature_configs_dir
    # dash_data.plot_configs_dir=plot_configs_dir
    dash_data.feature_config_default=feature_config_default
    dash_data.plot_config_default=plot_config_default

    dash_data.init_db()

    # if start_dir:
    #     dash_data.file_tracker.update(start_dir)

    # if not external_stylesheets:
    #     external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

    # app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
    app.layout = get_layout(
        input_dir=input_dir,
        dash_data=dash_data,
        chart_offset=default_chart_offset,
        feature_config_initial=feature_config_initial,
        plot_config_initial=plot_config_initial,
    )

    # callbacks.files.file_table_callback(app, gdd, input_dir)
    # callbacks.market.market_callback(app, gdd, input_dir)
    # callbacks.figure.figure_callback(app, gdd, input_dir)
    # callbacks.orders.orders_callback(app, gdd, input_dir)
    # callbacks.featureconfigs.feature_configs_callback(app, gdd, input_dir)
    # callbacks.libs.libs_callback(app)
    # callbacks.log.log_callback(app)
    # callbacks.db.db_callback(app, gdd)

    active_logger.info(f'Dash version: {dash.__version__}')
    active_logger.info(f'Dash renderer version: {dash_renderer.__version__}')
    active_logger.info('Starting dash server...')

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False)
    # waitress.serve(app.server, threads=4)



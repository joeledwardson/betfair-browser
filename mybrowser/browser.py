from __future__ import annotations
import dash
import dash_renderer
import logging
import sys
from .layout import get_layout
from . import callbacks
import dash
import dash_bootstrap_components as dbc
from mybrowser.session.session import Session
from mybrowser.session.config import init as config_init

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)
FA = "https://use.fontawesome.com/releases/v5.15.1/css/all.css"


def run_browser(debug: bool, config_path=None):
    """
    run dash app mybrowser - input_dir specifies input directory for entry point for mybrowser but also expected root for:
    - "historical" dir
    - "recorded" dir
    """
    if sys.version_info < (3, 9):
        raise Exception('Python version needs to be 3.9 or higher!')

    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, FA])
    session = Session()

    config = config_init(config_path)
    db_kwargs = {}
    if config.has_section('DB_CONFIG'):
        db_kwargs = config['DB_CONFIG']

    session.init_db(**db_kwargs)
    session.init_config(config)

    callbacks.cb_runners(app, session)
    callbacks.cb_orders(app, session)
    callbacks.cb_market(app, session)
    callbacks.cb_logs(app, session)
    callbacks.cb_libs(app, session)
    callbacks.cb_configs(app, session)
    callbacks.cb_fig(app, session)

    app.layout = get_layout(
        n_odr_rows=int(config['TABLE']['orders_rows']),
        n_tmr_rows=int(config['TABLE']['timings_rows']),
        filter_margins=config['LAYOUT']['filter_margins'],
        dflt_offset=config['PLOT_CONFIG']['default_offset'],
        mkt_tbl_cols=dict(config['TABLE_COLS']),
        n_mkt_rows=int(config['TABLE']['market_rows']),
        n_run_rows=int(config['TABLE']['runner_rows'])
    )

    active_logger.info(f'Dash version: {dash.__version__}')
    active_logger.info(f'Dash renderer version: {dash_renderer.__version__}')
    active_logger.info('Starting dash server...')

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False)


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
from . import config
# from .session.conn import Conn
from mytrading.utils import bettingdb

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def run_browser(debug: bool, config_path=None):
    """
    run dash app mybrowser - input_dir specifies input directory for entry point for mybrowser but also expected root for:
    - "historical" dir
    - "recorded" dir
    """
    if sys.version_info < (3, 9):
        raise Exception('Python version needs to be 3.9 or higher!')

    # Conn.session = bettingdb.BettingDB(**(db_kwargs or {}))

    config.init(config_path)
    db_kwargs = {}
    if config.config.has_section('DB_CONFIG'):
        db_kwargs = config.config['DB_CONFIG']
    dash_data.init_db(**db_kwargs)

    dash_data.init_config(config.config)
    app.layout = get_layout()

    active_logger.info(f'Dash version: {dash.__version__}')
    active_logger.info(f'Dash renderer version: {dash_renderer.__version__}')
    active_logger.info('Starting dash server...')

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False)




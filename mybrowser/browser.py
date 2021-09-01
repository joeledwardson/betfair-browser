from __future__ import annotations
import dash
import dash_renderer
import dash_bootstrap_components as dbc
import logging
import sys
from configparser import ConfigParser
from .layout import generate_layout
from .session import Session
from flask_caching import Cache
from . import components

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)
FA = "https://use.fontawesome.com/releases/v5.15.1/css/all.css"


def get_app(config_path=None):
    """
    run dash app mybrowser - input_dir specifies input directory for entry point for mybrowser but also expected root for:
    - "historical" dir
    - "recorded" dir
    """
    if sys.version_info < (3, 9):
        raise ImportError('Python version needs to be 3.9 or higher!')

    app = dash.Dash(__name__, title='Betfair Browser', update_title=None, external_stylesheets=[dbc.themes.BOOTSTRAP, FA])
    cache = Cache()
    cache.init_app(app.server, config={'CACHE_TYPE': 'simple'})

    if config_path:
        config = ConfigParser()
        config.read_file(config_path)
    else:
        config = None
    session = Session(cache, config)

    _comps = [
        components.MarketComponent(),
        components.RunnersComponent(),
        components.FigureComponent(),
        components.StrategyComponent(),
        components.OrdersComponent(),
        components.LibraryComponent(),
        components.TimingsComponent()
    ]
    notifications = [c.NOTIFICATION_ID for c in _comps if c.NOTIFICATION_ID]
    _comps.append(components.LoggerComponent(notifications))
    components.components_callback(app, _comps)

    for c in _comps:
        c.callbacks(app, session)
    layout_spec = components.components_layout(_comps, 'Betfair Browser', session.config)
    app.layout = generate_layout(layout_spec)

    return app



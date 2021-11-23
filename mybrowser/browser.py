from __future__ import annotations
import dash
import dash_bootstrap_components as dbc
import logging
import sys
from typing import Optional, Dict, Any
import importlib.resources as pkg_resources
from flask_caching import Cache
import yaml
from dash_extensions.enrich import DashProxy, MultiplexerTransform

import myutils.dashutilities.component
from myutils.dashutilities.layout import generate_layout
from .session import Session
from . import components
from myutils import dictionaries

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)
FA = "https://use.fontawesome.com/releases/v5.15.1/css/all.css"


def get_app(config_path=None, additional_config: Optional[Dict[str, Any]] = None):
    if sys.version_info < (3, 9):
        raise ImportError('Python version needs to be 3.9 or higher!')

    app = DashProxy(
        name=__name__,
        title='Betfair Browser 🏇',
        update_title=None,
        external_stylesheets=[dbc.themes.BOOTSTRAP, FA],
        transforms=[MultiplexerTransform()]
    )
    cache = Cache()
    cache.init_app(app.server, config={'CACHE_TYPE': 'simple'})

    if config_path:
        with open(config_path, 'r') as f:
            data = f.read()
    else:
        data = pkg_resources.read_text("mybrowser.session", 'config.yaml')
    config = yaml.load(data, yaml.FullLoader)

    if additional_config:
        dictionaries.dict_update(additional_config, config)
    session = Session(cache, config)

    _comps = [
        components.OverviewComponent(),
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
    myutils.dashutilities.component.components_callback(app, _comps)

    for c in _comps:
        c.callbacks(app, session, config)
    layout_spec = myutils.dashutilities.component.components_layout(_comps, 'Betfair Browser 🏇', session.config)
    app.layout = generate_layout(layout_spec)

    return app



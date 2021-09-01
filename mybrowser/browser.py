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


def run_browser(debug: bool, config_path=None):
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

    # callbacks.cb_runners(app, session)
    # callbacks.cb_orders(app, session)
    # callbacks.cb_market(app, session)
    # callbacks.cb_logs(app, session)
    # callbacks.cb_libs(app, session)
    # callbacks.cb_configs(app, session)
    # callbacks.cb_fig(app, session)
    # callbacks.cb_strategy(app, session)
    # callbacks.cb_display(app)


    # layout_spec = layouts.get_bf_layout(session.config)
    for c in _comps:
        c.callbacks(app, session)
    layout_spec = components.components_layout(_comps, 'Betfair Browser', session.config)
    app.layout = generate_layout(layout_spec)

    active_logger.info(f'Dash version: {dash.__version__}')
    active_logger.info(f'Dash renderer version: {dash_renderer.__version__}')
    active_logger.info('Starting dash server...')

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False, use_reloader=False)


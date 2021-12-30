from __future__ import annotations

from configparser import ConfigParser

import dash
import dash_bootstrap_components as dbc
import logging
import sys
from typing import Optional, Dict, Any, List
import importlib.resources as pkg_resources
from flask_caching import Cache
import yaml
from dash_extensions.enrich import DashProxy, MultiplexerTransform
from dash import html
from dash import dcc
from myutils.dashutilities import interface as comp

from myutils import general
from .session.session import Session
from .session.config import MarketFilter, get_market_filters
from . import components
from myutils import dictionaries


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)
FA = "https://use.fontawesome.com/releases/v5.15.1/css/all.css"
MD = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.1.0/github-markdown.min.css"


def not_none(lst: List[Any]) -> List[Any]:
    return [x for x in lst if x is not None]


def get_header(
        loading_ids: List[str],
        config: ConfigParser,
        comps: List[components.Component],
        padding_y=2,
        padding_x=4
) -> dbc.Row:
    return dbc.Row([
        dbc.Col(width=3),
        dbc.Col(
            dbc.Row(
                dbc.Col(html.H1('Betfair Browser 🏇'), width='auto'),
                justify='center',
                align='center'
            ),
            width=6,
        ),
        dbc.Col(
            comp.div(
                'right-header',
                css_classes='d-flex',
                content=[
                    comp.loading(
                        'loading-container',
                        content=[comp.div(l_id) for l_id in loading_ids]
                    ),
                    comp.div('header-buffer', css_classes='flex-grow-1'),
                    *not_none([c.header_right(config) for c in comps])
                ]
            ),
            width=3
        )],
        align='center',
        className=f'bg-light py-{padding_y} px-{padding_x}'
    )


def get_nav(navs: List[dbc.NavItem], item_padding=0, nav_padding=2) -> html.Div:
    return html.Div(
        dbc.Nav(
            [html.Div(x, className=f'p-{item_padding}') for x in navs],
            vertical=True,
            # pills=True,
            className=f'h-100 pt-{nav_padding}',
        ),
        id='nav-bar',
    )


def get_app(config_path=None, additional_config: Optional[Dict[str, Any]] = None):
    if sys.version_info < (3, 9):
        raise ImportError('Python version needs to be 3.9 or higher!')

    app = DashProxy(
        name=__name__,
        title='Betfair Browser 🏇',
        update_title=None,
        external_stylesheets=[dbc.themes.BOOTSTRAP, FA, MD],
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
    market_filters = get_market_filters()
    session = Session(cache, config, market_filters)

    _comps = [
        components.OverviewComponent(),
        components.MarketComponent(market_filters),
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
        c.callbacks(app, session, config)

    loading_ids = [c.loading_ids() for c in _comps]
    loading_ids = [item for sublist in loading_ids for item in sublist]


    containers = not_none([c.display_spec(config) for c in _comps])
    sidebars = not_none([c.sidebar(config) for c in _comps])
    navs = not_none([c.nav_item(config) for c in _comps])
    nav = get_nav(navs)
    header = get_header(loading_ids, config, _comps)
    stores = [comp.store(store_id) for store_id in notifications]
    stores += general.flatten([c.additional_stores() for c in _comps])

    app.layout = html.Div([
        dcc.Location(id="url"),
        html.Div(general.flatten([c.modals(config) for c in _comps])),
        html.Div(stores),
        html.Div(
            [
                header,
                html.Div(
                    [nav] + containers + sidebars,
                    className='d-flex flex-row flex-grow-1 overflow-hidden'
                ),
                html.Div(id='toast-holder'),
                html.Div(id='test-div')
            ],
            id='browser-container',
            className='d-flex flex-column'
        ),
        html.Div(general.flatten([c.tooltips(config) for c in _comps]))
    ])

    return app



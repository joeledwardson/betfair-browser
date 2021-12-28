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
import itertools
import dash_bootstrap_components as dbc
from dash import html
from dash import dcc
from dash import dash_table

import myutils.dashutilities.component
from myutils.dashutilities.layout import generate_layout
from .session import Session
from . import components
from myutils import dictionaries
from myutils.dashutilities.layout import generate_header, _gen_element, generate_sidebar, generate_nav, generate_container

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

    loading_ids = [c.loading_ids() for c in _comps]
    loading_ids = [item for sublist in loading_ids for item in sublist]

    not_none = lambda lst: [x for x in lst if x is not None]
    layout_spec = myutils.dashutilities.layout.ContentSpec(**{
        'header_title': 'Betfair Browser 🏇',
        'header_left': {},
        'header_right': {
            'type': 'element-div',
            'css_classes': 'd-flex',
            'children_spec': [
                {
                    'type': 'element-loading',
                    'id': 'loading-container',
                    'children_spec': [
                        {
                            'type': 'element-div',
                            'id': l_id
                        } for l_id in loading_ids
                    ]
                },
                {
                    'type': 'element-div',
                    'css_classes': 'flex-grow-1'
                },
                *not_none([c.header_right(config) for c in _comps])
            ]
        },
        'navigation': not_none([c.nav_items(config) for c in _comps]),
        'hidden_elements': list(itertools.chain(*[c.modal_specs(config) for c in _comps])),
        'containers': not_none([c.display_spec(config) for c in _comps]),
        'sidebars': not_none([c.sidebar(config) for c in _comps]),
        'stores': list(itertools.chain(*[
            c.additional_stores() for c in _comps
        ])) + [{
            'id': c.NOTIFICATION_ID
        } for c in _comps if c.NOTIFICATION_ID],
        'tooltips': list(itertools.chain.from_iterable(c.tooltips(config) for c in _comps))
    })
    # layout_spec = myutils.dashutilities.component.components_layout(_comps, 'Betfair Browser 🏇', session.config)

    nav_spec = layout_spec.pop('navigation')
    nav = generate_nav(nav_spec)

    left_spec = layout_spec.pop('header_left')
    right_spec = layout_spec.pop('header_right')
    title = layout_spec.pop('header_title')
    header = generate_header(title, left_spec, right_spec)

    hidden_specs = layout_spec.pop('hidden_elements')
    hiddens = [_gen_element(x) for x in hidden_specs]

    container_specs = layout_spec.pop('containers')
    containers = [generate_container(x) for x in container_specs]

    sidebar_specs = layout_spec.pop('sidebars')
    sidebars = [generate_sidebar(x) for x in sidebar_specs]

    store_specs = layout_spec.get('stores', [])

    app.layout = html.Div([
        dcc.Location(id="url"),
        html.Div(hiddens),
        html.Div([
            dcc.Store(s['id'], storage_type=s.get('storage_type', 'session'), data=s.get('data', None))
            for s in store_specs
        ]),
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
        html.Div([_gen_element(s) for s in layout_spec['tooltips']])
    ])

    # app.layout = generate_layout(layout_spec)

    return app



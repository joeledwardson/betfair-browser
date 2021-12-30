from __future__ import annotations
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
from .session.config import MarketFilter, get_market_filters, Config, get_strategy_filters
from . import components


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)
FA = "https://use.fontawesome.com/releases/v5.15.1/css/all.css"
MD = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.1.0/github-markdown.min.css"


def not_none(lst: List[Any]) -> List[Any]:
    return [x for x in lst if x is not None]


def get_header(
        loading_ids: List[str],
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
                    *not_none([c.header_right() for c in comps])
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


def get_app(config: Config):
    if sys.version_info < (3, 10):
        raise ImportError('Python version needs to be 3.10 or higher!')

    app = DashProxy(
        name=__name__,
        title='Betfair Browser 🏇',
        update_title=None,
        external_stylesheets=[dbc.themes.BOOTSTRAP, FA, MD],
        transforms=[MultiplexerTransform()]
    )
    cache = Cache()
    cache.init_app(app.server, config={'CACHE_TYPE': 'simple'})

    market_filters = get_market_filters(config.database_config.market_date_format)
    strategy_filters = get_strategy_filters(config.database_config.strategy_date_format)

    session = Session(cache, config, market_filters, strategy_filters)

    runner_button_id = 'button-runners'
    _comps = [
        components.OverviewComponent(
            pathname="/",
            container_id="container-overview"
        ),
        components.MarketComponent(
            pathname='/markets',
            container_id='container-market',
            notification_id='notifications-market',
            sidebar_id='container-filters-market',
            loading_id='market-loading',
            market_filters=market_filters,
            sort_options=config.table_configs.market_sort_options,
            table_columns=config.table_configs.market_table_cols,
            n_table_rows=config.table_configs.market_rows,
            runner_button_id=runner_button_id,
            enable_cache=config.display_config.cache
        ),
        components.RunnersComponent(
            pathname='/runners',
            container_id = 'container-runners',
            notification_id = 'notifications-runners',
            sidebar_id = 'container-filters-plot',
            loading_id = 'runners-loading',
            table_columns=config.table_configs.runner_table_cols,
            n_table_rows=config.table_configs.runner_rows,
            default_offset=config.plot_config.default_offset,
            runner_button_id=runner_button_id,
            enable_reloads=config.display_config.config_reloads
        ),
        components.FigureComponent(
            pathname = '/figure',
            container_id = 'container-figures',
            notification_id = 'notifications-figure',
            loading_id = 'figures-loading'
        ),
        components.StrategyComponent(
            notification_id = 'notifications-strategy',
            pathname = '/strategy',
            container_id = 'container-strategy',
            sidebar_id = 'container-filters-strategy',
            table_columns=config.table_configs.strategy_table_cols,
            n_table_rows=config.table_configs.strategy_rows,
            enable_delete=config.display_config.strategy_delete
        ),
        components.OrdersComponent(
            notification_id = 'notifications-orders',
            pathname = '/orders',
            container_id = 'container-orders',
            table_columns=config.table_configs.order_table_cols,
            n_table_rows=config.table_configs.orders_rows,
            runner_button_id=runner_button_id
        ),
        components.TimingsComponent(
            pathname = '/timings',
            container_id = 'container-timings',
            table_columns=config.table_configs.timings_table_cols,
            n_table_rows=config.table_configs.timings_rows
        )
    ]
    if config.display_config.libraries:
        _comps.append(components.LibraryComponent(
            loading_id='loading-out-libs',
            notification_id='notifications-libs'
        ))

    notifications = [c.notification_id for c in _comps if c.notification_id]
    _comps.append(components.LoggerComponent(
        pathname = '/logs',
        container_id = 'container-logs',
        stores=notifications
    ))
    components.components_callback(app, _comps)

    for c in _comps:
        c.callbacks(app, session)

    loading_ids = [c.loading_ids() for c in _comps]
    loading_ids = [item for sublist in loading_ids for item in sublist]


    containers = not_none([c.display_spec() for c in _comps])
    sidebars = not_none([c.sidebar() for c in _comps])
    navs = not_none([c.nav_item() for c in _comps])
    nav = get_nav(navs)
    header = get_header(loading_ids, _comps)
    stores = [comp.store(store_id) for store_id in notifications]
    stores += general.flatten([c.additional_stores() for c in _comps])

    app.layout = html.Div([
        dcc.Location(id="url"),
        html.Div(general.flatten([c.modals() for c in _comps])),
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
        html.Div(general.flatten([c.tooltips() for c in _comps]))
    ])

    return app



import itertools

from dash.development import base_component as dbase
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
import dash_table
from dash.development.base_component import Component
from typing import Dict, List, Any, Optional
import copy
import myutils.mydash
from myutils import myregistrar
from .exceptions import LayoutException
from .layouts import market, runners, configs, orders, timings, logger, strategy, INTERMEDIARIES
import uuid

NAV_BTN_P = 0  # padding for navigation buttons
LOAD_TYPE = 'dot'  # loading type
NAV_PT = 2  # top padding of nav bar
BTN_ML = 2  # left margin for button icons
BTN_COLOR = 'primary'  # default button color
COL_PAD = 1  # column padding
CONT_M = 4  # container margins
CONT_P = 4  # container padding
SIDE_EACH_MB = 2  # bottom margin for each sidebar element
SIDE_EACH_MX = 1  # left/right margin for each sidebar element
SIDE_CONTENT_P = 3  # sidebar content padding
SIDE_PR = 2  # sidebar padding right of elements
SIDE_PL = 1

EL_MAP = {
    'element-header': {
        'dash_cls': html.H2,
    },
    'element-div': {
        'dash_cls': html.Div
    },
    'element-input': {
        'dash_cls': dbc.Input
    },
    'element-progress': {
        'dash_cls': dbc.Progress
    },
    'element-input-group': {
        'dash_cls': dbc.InputGroup
    },
    'element-input-group-addon': {
        'dash_cls': dbc.InputGroupAddon
    }
}


nav_spec = [
    {
        'type': 'element-navigation-item',
        'href': '/',
        'nav_icon': 'fas fa-horse',
    },
    {
        'type': 'element-navigation-item',
        'href': '/strategy',
        'nav_icon': 'fas fa-chess-king'
    },
    {
        'type': 'element-navigation-item',
        'href': '/runners',
        'nav_icon': 'fas fa-running',
    },
    {
        'type': 'element-navigation-item',
        'href': '/timings',
        'nav_icon': 'fas fa-clock'
    },
    {
        'type': 'element-navigation-item',
        'href': '/orders',
        'nav_icon': 'fas fa-file-invoice-dollar'
    },
    {
        'type': 'element-navigation-item',
        'href': '/logs',
        'nav_icon': 'fas fa-envelope-open-text',
        'css_classes': 'position-relative',
        'nav_children_spec': [
            {
                'type': 'element-div',
                'id': 'msg-alert-box',
                'css_classes': 'right-corner-box',
                'hidden': True,
                'children_spec': [
                    {
                        'type': 'element-badge',
                        'id': 'log-warns',
                        'color': 'danger',
                        'css_classes': 'p-2'
                    }
                ]
            }
        ]
    }
]


def _validate_id(spec):
    if spec.get('id') is None:
        raise LayoutException(f'spec "{spec}" has no ID')

dash_generators = myregistrar.MyRegistrar()



@dash_generators.register_named('element-select')
def gen_select(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    return dcc.Dropdown(
        id=spec.pop('id'),
        placeholder=spec.pop('placeholder', None),
        className=spec.pop('css_classes', '')
    )


@dash_generators.register_named('element-button')
def gen_button(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    children = list()
    btn_text = spec.pop('btn_text', None)
    if btn_text is not None:
        children.append(btn_text)
    btn_icon = spec.pop('btn_icon', None)
    btn_color = spec.pop('color', BTN_COLOR)
    if btn_icon is not None:
        btn_cls = btn_icon
        if btn_text is not None:
            btn_cls += f' ml-{BTN_ML}'  # add margin left to icon if text is specified
        children.append(html.I(className=btn_cls))
    return dbc.Button(
        children,
        id=spec.pop('id'),
        n_clicks=0,
        color=btn_color,
        className=spec.pop('css_classes', '')
    )


@dash_generators.register_named('element-table')
def gen_table(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    table_cols = spec.pop('columns')
    n_rows = spec.pop('n_rows')
    table_id = spec.pop('id')
    style_cell = {
        'textAlign': 'left',
        'whiteSpace': 'normal',
        'height': 'auto',
        'verticalAlign': 'middle',
        'padding': '0.5rem',
    }
    if not spec.pop('no_fixed_widths', None):
        style_cell |= {
            'maxWidth': 0  # fix columnd widths
        }
    return html.Div(
        dash_table.DataTable(
            id=table_id,
            columns=[
                dict(name=v, id=k)
                for k, v in table_cols.items()
            ],
            style_cell=style_cell,
            style_data={
                'border': 'none'
            },
            style_header={
                'fontWeight': 'bold',
                'border': 'none'
            },
            style_table={
                'overflowY': 'auto',
            },
            page_size=n_rows,
        ),
        className='table-container flex-grow-1 overflow-hidden'
    )


@dash_generators.register_named('element-stylish-select')
def gen_stylish_select(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    placeholder = spec.pop('placeholder')
    options = spec.pop('select_options', list())
    clear_id = spec.pop('clear_id')
    select_id = spec.pop('id')
    css_classes = spec.pop('css_classes', '')
    return dbc.ButtonGroup(
        [
            dbc.Select(
                id=select_id,
                placeholder=placeholder,
                options=options,
            ),
            dbc.Button(
                [html.I(className="fas fa-times-circle")],
                id=clear_id,
                color='secondary'
            ),
        ], 
        className=css_classes
    )


@dash_generators.register_named('element-navigation-button')
def gen_navigation_button(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    href = spec.pop('href')
    btn_id = spec.pop('btn_id', None)
    btn_icon = spec.pop('btn_icon')
    nav_id = spec.pop('id')
    css_classes = spec.pop('css_classes', '')
    return dbc.NavLink(
        [dbc.Button(
            html.I(className=btn_icon),
            id=btn_id,
            n_clicks=0,
            color=BTN_COLOR,
        )],
        id=nav_id,
        href=href,
        active='exact',
        className=f'p-{NAV_BTN_P}' or css_classes
    )


@dash_generators.register_named('element-navigation-item')
def gen_navigation_item(spec: Dict) -> dbase.Component:
    nav_icon = spec.pop('nav_icon')
    css_classes = spec.pop('css_classes', '')
    children = list()
    if nav_icon:
        children.append(html.I(className=nav_icon))
    children += [_gen_element(x) for x in spec.pop('nav_children_spec', list())]
    return dbc.NavItem(
        dbc.NavLink(
            children,
            href=spec.pop('href'),
            active='exact',
        ),
        className=css_classes
    )


@dash_generators.register_named('element-loading')
def gen_navigation_item(spec: Dict) -> dbase.Component:
    _validate_id(spec)
    return dcc.Loading(
        html.Div(id=spec.pop('id')),
        type=LOAD_TYPE,
        className=spec.pop('css_classes', '')
    )


@dash_generators.register_named('element-badge')
def gen_navigation_item(spec: Dict) -> dbase.Component:
    return dbc.Badge(
        id=spec.pop('id', None) or str(uuid.uuid4()),
        color=spec.pop('color', None),
        className=spec.pop('css_classes', '')
    )


@dash_generators.register_named('element-modal')
def gen_modal(spec: Dict) -> dbase.Component:
    modal_id = spec.pop('id')
    header_spec = spec.pop('header_spec')
    header_children = _gen_element(header_spec) if type(header_spec) == list else header_spec
    footer_spec = spec.pop('footer_spec')
    footer_children = list()
    for i, child_spec in enumerate(footer_spec):
        if i == 0:
            css_classes = child_spec.get('css_classes', '')
            css_classes += ' ml-auto'
            child_spec['css_classes'] = css_classes
        footer_children.append(_gen_element(child_spec))
    return dbc.Modal([
        dbc.ModalHeader(header_children),
        dbc.ModalFooter(footer_children)
    ], id=modal_id)


def _gen_element(spec: Dict):
    el_type = spec.pop('type')
    
    if el_type in dash_generators:
        element = dash_generators[el_type](spec)
    elif el_type in EL_MAP:
        dash_cls = EL_MAP[el_type]['dash_cls']
        children = spec.pop('children_spec', None)
        user_kwargs = spec.pop('element_kwargs', dict())
        hidden = spec.pop('hidden', None)
        el_id = spec.pop('id', None)
        if type(children) == list:
            child_elements = list()
            for child_spec in children:
                child_elements.append(_gen_element(child_spec))
            children = child_elements
        el_kwargs = {'id': el_id} if el_id else {}
        el_kwargs |= {'hidden': hidden} if hidden else {}
        el_kwargs |= {'children': children, 'className': spec.pop('css_classes', '')}
        el_kwargs |= EL_MAP[el_type].get('default_kwargs', dict())
        el_kwargs |= user_kwargs
        element = dash_cls(**el_kwargs)
    else:
        raise LayoutException(f'type "{el_type}" unrecognised')

    if spec:
        raise LayoutException(f'spec "{spec}" has unrecognised elements')
    return element


def generate_sidebar(spec: Dict):
    title = spec.pop('sidebar_title')
    sidebar_id = spec.pop('sidebar_id')
    close_id = spec.pop('close_id')
    sidebar_content_spec = spec.pop('content')
    children = list()
    for row_spec in sidebar_content_spec:
        children.append(
            html.Div(
                _gen_element(row_spec),
                className=f'mb-{SIDE_EACH_MB} mx-{SIDE_EACH_MX}'
            )
        )
    return html.Div(
        html.Div([
            dbc.Row([
                dbc.Col(html.H2(title)),
                dbc.Col(dbc.Button('Close', id=close_id), width='auto')],
                align='center'
            ),
            html.Hr(className='ml-0 mr-0'),
            html.Div(
                children,
                className=f'd-flex flex-column pr-{SIDE_PR} overflow-auto'  # allow space for scroll bar with padding right
            )],
            className=f'd-flex flex-column h-100 p-{SIDE_CONTENT_P}'
        ),
        className='right-side-bar',
        id=sidebar_id
    )


def generate_containers(spec: Dict):
    cont_id = spec.pop('container-id')
    cont_children = []
    content_spec = spec.pop('content')
    if type(content_spec) != list:
        raise LayoutException(f'expected content to be list, instead got "{type(content_spec)}"')
    for row_spec in content_spec:
        if type(row_spec) == list:
            row_children = list()
            for i, col_spec in enumerate(row_spec):
                row_children.append(dbc.Col(
                    _gen_element(col_spec),
                    width='auto',
                    className=f'pr-{COL_PAD}' if i == 0 else f'p-{COL_PAD}'
                ))
            cont_children.append(dbc.Row(
                row_children,
                align='center'
            ))
        elif type(row_spec) == dict:
            cont_children.append(_gen_element(row_spec))
        else:
            raise LayoutException(f'expected row spec list/dict, got "{type(row_spec)}"')
    containers = [
        html.Div(
            html.Div(
                cont_children,
                className='d-flex flex-column h-100'
            ),
            className=f'flex-grow-1 shadow m-{CONT_M} p-{CONT_P}',
            id=cont_id,
        )
    ]
    sidebar_spec = spec.pop('sidebar', None)
    if sidebar_spec is not None:
        containers.append(
            generate_sidebar(sidebar_spec)
        )
    return containers


def strategy_modal():
    return dbc.Modal(
        [
            dbc.ModalHeader("Delete strategy?"),
            dbc.ModalFooter([
                dbc.Button("Yes", id="strategy-delete-yes", color='danger', className='ml-auto'),
                dbc.Button("No", id="strategy-delete-no", color='success')
            ]),
        ],
        id="strategy-delete-modal",
    )


# TODO - move all loading bars to top
def hidden_elements(n_odr_rows, n_tmr_rows):
    return [
        _gen_element(strategy.strategy_modal()),
        # strategy_modal(),
        # TODO - make orders its own page
        # dbc.Modal([
        #     dbc.ModalHeader("Orders"),
        #     dbc.ModalBody(orders.table(n_odr_rows)),
        #     dbc.ModalFooter(
        #         dbc.Button("Close", id="modal-close-orders", className="ml-auto")
        #     )],
        #     id="modal-orders",
        #     size="xl"
        # ),

        # hidden divs for intermediary output components
        *[myutils.mydash.hidden_div(x) for x in INTERMEDIARIES],

        dcc.Interval(
            id='interval-component',
            interval=1 * 1000,  # in milliseconds
            n_intervals=0
        )

    ]


def header(right_children, left_children):

    end = dbc.Row([
        dbc.Col([
            dcc.Loading(
                html.Div(id='loading-out-header'),
                type='dot'
            )
        ] + right_children),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-book-open"),
                id='button-libs',
                color='info'
            ),
            width='auto',
            className='p-1'
        )],
        align='center',
        no_gutters=True,
    )

    return dbc.Row([
        dbc.Col(
            left_children,
            width=3
        ),
        dbc.Col(
            dbc.Row(
                dbc.Col(html.H1('Betfair Browser'), width='auto'),
                justify='center',
                align='center'
            ),
            width=6,
        ),
        dbc.Col(
            end,
            width=3
        )],
        align='center',
        className='bg-light py-2 px-4'
    )


def plot_filter_div(filter_margins, dflt_offset):
    return html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Plot Config')),
                    dbc.Col(dbc.Button('close', id='btn-plot-close'), width='auto')],
                    align='center',
                ),
                html.Hr(className='ml-0 mr-0'),
                configs.inputs(filter_margins, dflt_offset)
            ],
            className='d-flex flex-column h-100 p-3'
        ),
        className='right-side-bar',
        id='container-filters-plot'
    )


def market_div(mkt_tbl_cols, n_mkt_rows, market_sort_options):
    return html.Div(
        html.Div(
            [
                market.header(),
                market.mkt_buttons(market_sort_options),
                market.query_status(),
                market.mkt_table(mkt_tbl_cols, n_mkt_rows)
            ],
            className='d-flex flex-column h-100'
        ),
        className='flex-grow-1 shadow m-4 p-4',
        id='container-market'
    )


def market_filter_div(filter_margins):
    return html.Div(
        html.Div([
            dbc.Row([
                dbc.Col(html.H2('Market Filters')),
                dbc.Col(dbc.Button('close', id='btn-right-close'), width='auto')],
                align='center'
            ),
            html.Hr(className='ml-0 mr-0'),
            html.Div(
                [
                    *market.mkt_filters(multi=False, filter_margins=filter_margins),
                    html.Hr(className='ml-0 mr-0'),
                    *market.strat_filters(filter_margins),
                ],
                className='d-flex flex-column pr-2 overflow-auto'
            )],
            className='d-flex flex-column h-100 p-3'
        ),
        className='right-side-bar',
        id='container-filters-market'
    )


def strat_filter_div(filter_margins):
    return html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Strategy Filters')),
                    dcc.Dropdown(
                        id='input-strategy-select',
                        placeholder='Strategy...',
                        className=filter_margins,
                        optionHeight=60,
                    ),
                    dbc.Col(dbc.Button('close', id='btn-strategy-close'), width='auto'),
                ], align='center'),
                html.Hr(),
            ],
            className='d-flex flex-column h-100 p-3'
        ),
        className='right-side-bar',
        id='container-filters-strategy'
    )


def runners_div(n_run_rows):
    return html.Div([
        runners.header(),
        runners.inputs(),
        runners.market_info(),
        runners.table(n_run_rows)
    ], className='flex-grow-1 shadow m-4 p-4 overflow-auto', id='container-runners')


def timings_div(n_tmr_rows):
    return html.Div(
        [
            html.H2('Timings'),
            timings.table(n_tmr_rows)
        ],
        id='container-timings',
        className='shadow m-4 p-4 flex-grow-1 overflow-auto'
    )


def log_div():
    return html.Div(
        html.Div(
            [
                html.H2('Python Log'),
                logger.log_box()
            ],
            className='d-flex flex-column h-100'
        ),
        className='flex-grow-1 shadow m-4 p-4 overflow-auto',
        id='container-logs'
    )


def strat_div(n_strat_rows, strat_cols):
    full_strat_cols = strat_cols | {
        'n_markets': 'Market Count',
        'total_profit': 'Total Profit'
    }
    return html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Strategies'), width='auto'),
                    dbc.Col(
                        dbc.Button(
                            html.I(className="fas fa-filter"),
                            id="btn-strategy-filter",
                            n_clicks=0,
                            color='primary'
                        ),
                        width='auto',
                        className='p-1'
                    ),
                    dbc.Col(
                        dbc.NavLink(
                            dbc.Button(
                                html.I(className="fas fa-download"),
                                id="btn-strategy-download",
                                n_clicks=0,
                                color='primary'
                            ),
                            href="/",
                            active="exact",
                            className='p-0',
                            id='nav-strategy-download',
                        ),
                        width='auto',
                        className='p-1'
                    )
                ], align='center'),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            ['Reload', html.I(className="fas fa-sync-alt ml-2")],
                            id="btn-strategy-refresh",
                            n_clicks=0,
                            color='primary'
                        ),
                        width='auto',
                        className='pr-1'
                    ),
                    dbc.Col(
                        dbc.Button(
                            ['Delete Strategy', html.I(className="fas fa-trash ml-2")],
                            id="btn-strategy-delete",
                            n_clicks=0,
                            color='danger'
                        ),
                        width='auto',
                        className='p-1'
                    ),
                ], align='center'),
                dbc.Row([
                    dbc.Col(
                        dbc.Select(
                            id='input-strategy-run',
                            placeholder='Strategy config...',
                        ),
                        width='auto',
                        className='pr-1'
                    ),
                    dbc.Col(
                        dbc.Button(
                            'Reload configs...',
                            id='btn-strategies-reload',
                            n_clicks=0,
                            color='info',
                        ),
                        width='auto',
                        className='p-1'
                    ),
                    dbc.Col(
                        dbc.Button(
                            ['Run Strategy', html.I(className="fas fa-play-circle ml-2")],
                            id="btn-strategy-run",
                            n_clicks=0,
                        ),
                        width='auto',
                        className='p-1'
                    ),
                ], align='center'),
                html.Div(
                    dash_table.DataTable(
                        id='table-strategies',
                        columns=[
                            {"name": v, "id": k}
                            for k, v in full_strat_cols.items()
                        ],
                        style_cell={
                            'textAlign': 'left',
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'maxWidth': 0,  # fix column widths
                            'verticalAlign': 'middle',
                            'padding': '0.5rem',
                        },
                        style_data={
                            'border': 'none'
                        },
                        css=[{
                            'selector': 'td.dash-cell',
                            'rule': 'overflow-wrap: anywhere;'
                        }],
                        style_header={
                            'fontWeight': 'bold',
                            'border': 'none'
                        },
                        # the width and height properties below are just placeholders
                        # when using fixed_rows with headers they cannot be relative or dash crashes - these are overridden in css
                        style_table={
                            'overflowY': 'auto',
                            # 'minHeight': '80vh', 'height': '80vh', 'maxHeight': '80vh',
                            # 'minWidth': '100vw', 'width': '100vw', 'maxWidth': '100vw'
                        },
                        # fixed_rows={
                        #     'headers': True,
                        #     'data': 0
                        # },
                        page_size=n_strat_rows,
                    ),
                    className='table-container flex-grow-1 overflow-hidden'
                )
            ],
            className='h-100 d-flex flex-column'
        ),
        className='flex-grow-1 shadow m-4 p-4 overflow-hidden',
        id='container-strategy'
    )


# TODO - add padding
nav_old = html.Div([
    dbc.Nav(
        [
            dbc.NavLink(
                [
                    html.I(className="fas fa-horse"),
                    html.Span("")
                ],
                href="/",
                active="exact",
                className='m-1'
            ),
            dbc.NavLink(
                [
                    html.I(className="fas fa-chess-king"),
                    html.Span(""),
                ],
                href="/strategy",
                active="exact",
            ),
            dbc.NavLink(
                [
                    html.I(className="fas fa-running"),
                    html.Span(""),
                ],
                href="/runners",
                active="exact",
            ),
            dbc.NavLink(
                [
                    html.I(className="fas fa-clock"),
                    html.Span(""),
                ],
                href="/timings",
                active="exact",
            ),
            dbc.NavLink(
                [
                    html.I(className="fas fas fa-envelope-open-text"),
                    html.Span(""),
                    html.Div(
                        dbc.Badge(id='log-warns', color="danger", className='p-2'),
                        id='msg-alert-box',
                        className='right-corner-box',
                        hidden=True
                    )
                ],
                href="/logs",
                active="exact",
                className='position-relative'
            ),
        ],
        vertical=True,
        pills=True,
        className='align-items-center h-100 pt-2'
    )
], id='nav-bar')

nav = html.Div(
    dbc.Nav(
        [html.Div(_gen_element(x), className='p-1') for x in nav_spec],
        vertical=True,
        pills=True,
        className=f'align-items-center h-100 pt-{NAV_PT}',
    ),
    id='nav-bar',
)

def get_layout(
        n_odr_rows,
        n_tmr_rows,
        filter_margins,
        dflt_offset,
        mkt_tbl_cols,
        n_mkt_rows,
        n_run_rows,
        market_sort_options,
        n_strat_rows,
        strat_tbl_cols,
        config
) -> html.Div:
    # container
    left_header_children = list()
    right_header_children = list()
    _confs = [
        logger.log_config_spec(config),
        market.market_display_spec(config),
        runners.runners_config_spec(config),
        strategy.strategy_config_spec(config),
        timings.timings_config_spec(config),
        orders.orders_config_spec(config),
    ]
    for _conf in _confs:
        left_header_children += [_gen_element(x) for x in _conf.pop('header_left', list())]
        right_header_children += [_gen_element(x) for x in _conf.pop('header_right', list())]

    return html.Div([
        dcc.Location(id="url"),
        html.Div(hidden_elements(n_odr_rows, n_tmr_rows)),
        html.Div(
            [
                header(right_header_children, left_header_children),
                html.Div(
                    [
                        nav,
                        # log_div(),
                        # market_div(mkt_tbl_cols, n_mkt_rows, market_sort_options),
                        # runners_div(n_run_rows),
                        # timings_div(n_tmr_rows),
                        # strat_div(n_strat_rows, strat_tbl_cols),
                        # *generate_containers(runners.runners_config_spec(config)),
                        # *generate_containers(market.market_display_spec(config)),
                        # strat_filter_div(filter_margins),
                        # market_filter_div(filter_margins),
                        # plot_filter_div(filter_margins, dflt_offset),
                    ] + list(itertools.chain(*[
                        generate_containers(c) for c in _confs
                    ])),
                    className='d-flex flex-row flex-grow-1 overflow-hidden'
                ),
                html.Div(id='toast-holder'),
            ],
            id='bf-container',
            className='d-flex flex-column'
        )
    ])

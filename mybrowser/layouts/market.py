import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table
from typing import Dict, List
import itertools
import json


def _sort_labels(sort_options: Dict) -> List[Dict]:
    return list(itertools.chain(*[
        [
            {
                'label': f'▲ {v}',
                'value': json.dumps({
                    'db_col': k,
                    'asc': True
                })
            },
            {
                'label': f'▼ {v}',
                'value': json.dumps({
                    'db_col': k,
                    'asc': False
                })
            }
        ]
        for k, v in sort_options.items()
    ]))


def market_display_spec(config):
    sort_options = dict(config['MARKET_SORT_OPTIONS'])
    n_mkt_rows = int(config['TABLE']['market_rows'])
    full_tbl_cols = dict(config['MARKET_TABLE_COLS'])
    options_labels = _sort_labels(sort_options)
    return {
        'container-id': 'container-market',
        'header_right': [
            {
                'type': 'element-loading',
                'id': 'loading-out-session'
            }
        ],
        'header_left': [
            {
                'type': 'element-div',
                'id': 'progress-container-div',
                'children_spec': [
                    {
                        'type': 'element-progress',
                        'id': 'header-progress-bar',
                        'element_kwargs': {
                            'striped': True,
                            'animated': True,
                        }
                    }
                ]
            }
        ],
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Market Browser',
                }, {
                    'type': 'element-button',
                    'id': 'btn-session-filter',
                    'btn_icon': 'fas fa-filter',
                }, {
                    'type': 'element-button',
                    'id': 'btn-db-reconnect',
                    'btn_icon': 'fas fa-database',
                }, {
                    'type': 'element-navigation-button',
                    'id': 'nav-runners',
                    'href': '/runners',
                    'btn_id': 'button-runners',
                    'btn_icon': 'fas fa-download'
                }
            ],
            [
                {
                    'type': 'element-button',
                    'id': 'btn-db-refresh',
                    'btn_icon': 'fas fa-sync-alt',
                    'btn_text': 'Reload'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-db-upload',
                    'btn_icon': 'fas fa-arrow-circle-up',
                    'btn_text': 'Upload Cache'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-cache-clear',
                    'btn_icon': 'fas fa-trash',
                    'btn_text': 'Clear Cache',
                    'color': 'warning'
                }
            ],
            [
                {
                    'type': 'element-stylish-select',
                    'id': 'market-sorter',
                    'placeholder': 'Market Sort...',
                    'select_options': options_labels,
                    'clear_id': 'btn-sort-clear'
                },
                {
                    'type': 'element-button',
                    'id': 'input-strategy-clear',
                    'btn_icon': 'fas fa-times-circle',
                    'btn_text': 'Clear Strategy',
                    'color': 'info'
                }
            ],
            [
                {
                    'type': 'element-div',
                    'id': 'market-query-status'
                }
            ],
            {
                'type': 'element-table',
                'id': 'table-market-session',
                'columns': full_tbl_cols,
                'n_rows': n_mkt_rows
            }
        ],
        'sidebar': {
            'sidebar_id': 'container-filters-market',
            'sidebar_title': 'Market Filters',
            'close_id': 'btn-right-close',
            'content': [
                {
                    'type': 'element-select',
                    'id': 'input-sport-type',
                    'placeholder': 'Sport...'
                },
                {
                    'type': 'element-select',
                    'id': 'input-mkt-type',
                    'placeholder': 'Market type...',
                },
                {
                    'type': 'element-select',
                    'id': 'input-bet-type',
                    'placeholder': 'Betting type...',
                },
                {
                    'type': 'element-select',
                    'id': 'input-format',
                    'placeholder': 'Format...'
                },
                {
                    'type': 'element-select',
                    'id': 'input-country-code',
                    'placeholder': 'Country...'
                },
                {
                    'type': 'element-select',
                    'id': 'input-venue',
                    'placeholder': 'Venue...'
                },
                {
                    'type': 'element-select',
                    'id': 'input-date',
                    'placeholder': 'Market date...'
                },
                {
                    'type': 'element-input',
                    'id': 'input-mkt-id',
                    'element_kwargs': {
                        'placeholder': 'Market ID filter...',
                    }
                },
                {
                    'type': 'element-button',
                    'id': 'input-mkt-clear',
                    'btn_icon': 'fas fa-times-circle',
                    'btn_text': 'Clear Filters'
                }
            ]
        }
    }


def header():
    return dbc.Row([
        dbc.Col(
            html.H2('Market Browser'),
            width='auto'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-filter"),
                id="btn-session-filter",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-database"),
                id="btn-db-reconnect",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.NavLink(
                [
                    dbc.Button(
                        html.I(className="fas fa-download"),
                        id='button-runners',
                        n_clicks=0,
                        color='primary'
                    )
                ],
                id="nav-runners",
                href="/runners",
                active="exact",
                className='p-0'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(),
        dbc.Col(

            className='anchor-right',
        )],
        align='center'
    )


def mkt_buttons(sort_options: Dict):
    options_labels = list(itertools.chain(*[
        [
            {
                'label': f'▲ {v}',
                'value': json.dumps({
                    'db_col': k,
                    'asc': True
                })
            },
            {
                'label': f'▼ {v}',
                'value': json.dumps({
                    'db_col': k,
                    'asc': False
                })
            }
        ]
        for k, v in sort_options.items()
    ]))
    return dbc.Row([
        dbc.Col(
            dbc.Button(
                ['Reload', html.I(className="fas fa-sync-alt ml-2")],
                id="btn-db-refresh",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='pr-1'
        ),
        dbc.Col(
            dbc.Button(
                ['Upload Cache', html.I(className="fas fa-arrow-circle-up ml-2")],
                id="btn-db-upload",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                ['Clear Cache', html.I(className="fas fa-trash ml-2")],
                id="btn-cache-clear",
                n_clicks=0,
                color='warning'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.ButtonGroup([
                dbc.Select(
                    id='market-sorter',
                    placeholder='Market Sort...',
                    options=options_labels,
                ),
                dbc.Button(
                    [html.I(className="fas fa-times-circle")],
                    id='btn-sort-clear',
                    color='secondary'
                ),
            ]),
            width='auto',
            className='p-1'
        ),
        # dbc.Col(
        #
        #     width='auto',
        #     className='p-1'
        # ),
        dbc.Col(
            dbc.Button(
                ['Clear Strategy', html.I(className="fas fa-times-circle ml-2")],
                id='input-strategy-clear',
                color='info'
            ),
            width='auto',
            className='p-1'
        )
    ], align='center')


def mkt_filters(multi, filter_margins):
    # market filters
    return [
        dcc.Dropdown(
            id='input-sport-type',
            placeholder='Sport...',
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-mkt-type',
            placeholder='Market type...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-bet-type',
            placeholder='Betting type...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-format',
            placeholder='Format...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-country-code',
            placeholder='Country...',
            # multi=multi,
            # optionHeight=60,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-venue',
            placeholder='Venue...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-date',
            placeholder='Market date...',
            multi=multi,
            className=filter_margins
        ),
        dbc.Input(
            id='input-mkt-id',
            placeholder='Market ID filter...',
            className=filter_margins
        ),

        dbc.Button(
            id='input-mkt-clear',
            children='Clear',
            className=filter_margins
        )
    ]


def query_status():
    # query text status
    return dbc.Row(dbc.Col(
        html.Div(id='market-query-status')
    ))


def mkt_table(tbl_cols, n_rows):
    # DB market browser
    full_tbl_cols = tbl_cols | {'market_profit': 'Profit'}
    return html.Div(
        dash_table.DataTable(
            id='table-market-session',
            columns=[
                {"name": v, "id": k}
                for k, v in full_tbl_cols.items()
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
            page_size=n_rows,
            # fixed_rows={
            #     'headers': True,
            #     'data': 0
            # },
        ),
        className='table-container flex-grow-1 overflow-hidden',
    )


def strat_filters(filter_margins):
    # strategy filters
    return [

    ]


import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table
from typing import Dict
import itertools
import json


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
            dbc.Select(
                id='market-sorter',
                placeholder='Market Sort...',
                options=options_labels,
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                ['Clear Sort', html.I(className="fas fa-times-circle ml-2")],
                id='btn-sort-clear',
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
            multi=multi,
            optionHeight=60,
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
        dcc.Input(
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
    return dbc.Row(dbc.Col(
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
                'verticalAlign': 'middle'
            },
            style_header={
                'fontWeight': 'bold'
            },
            page_size=n_rows,
        ),
        className='table-container'
    ))


def strat_filters(filter_margins):
    # strategy filters
    return [
        dcc.Dropdown(
            id='input-strategy-select',
            placeholder='Strategy...',
            className=filter_margins,
            optionHeight=60,
        ),
        dbc.Button(
            'Clear',
            id='input-strategy-clear',
            className=filter_margins
        ),
        dbc.Button(
            ['Delete Strategy', html.I(className="fas fa-trash ml-2")],
            id="btn-strategy-delete",
            n_clicks=0,
            color='danger'
        ),
    ]


def strat_buttons(filter_margins):
    return [
        dcc.Dropdown(
            id='input-strategy-run',
            placeholder='Strategy config...',
            className=filter_margins
        ),
        dbc.Button(
            'Reload configs...',
            id='btn-strategies-reload',
            n_clicks=0,
            color='info',
            className=filter_margins
        ),
        dbc.Button(
            ['Run Strategy', html.I(className="fas fa-play-circle ml-2")],
            id="btn-strategy-run",
            n_clicks=0,
            color='primary',
            className=filter_margins
        ),
    ]
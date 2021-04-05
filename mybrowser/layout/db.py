from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from ..config import config
from myutils.mydash import intermediate


def header():
    return html.Div(
        style={
            'display': 'grid',
            'grid-template-columns': 'auto auto auto',
            'align-items': 'center',
            'width': '100%',
        },
        children=[
            html.H2(
                children='Market Browser'
            ),
            html.Div(dbc.Button(
                html.I(className="fas fa-filter"),
                id="btn-db-filter",
                n_clicks=0,
            )),
            html.Div(
                className='loading-container',
                style={
                    'justify-self': 'end',
                },
                children=[
                    dcc.Loading(
                        id='loading-db',
                        type='dot',
                        children=html.Div(id='loading-out-db'),
                    )
                ]
            ),
        ]
    )


def filters(multi):
    # market filters
    return html.Div(
        style={
            'margin': '10px 0px',
            'width': '100%',
            'display': 'grid',
            'grid-template-columns': '1fr 1fr 1fr',
            'grid-row-gap': '2px',
            'grid-column-gap': '8px',
        },
        children=[
            dcc.Dropdown(
                id='input-sport-type',
                placeholder='Sport...'
            ),
            dcc.Dropdown(
                id='input-mkt-type',
                placeholder='Market type...',
                multi=multi,
            ),
            dcc.Dropdown(
                id='input-bet-type',
                placeholder='Betting type...',
                multi=multi,
            ),
            dcc.Dropdown(
                id='input-format',
                placeholder='Format...',
                multi=multi,
            ),
            dcc.Dropdown(
                id='input-country-code',
                placeholder='Country...',
                multi=multi,
                optionHeight=60,
            ),
            dcc.Dropdown(
                id='input-venue',
                placeholder='Venue...',
                multi=multi,
            ),
            dcc.Dropdown(
                id='input-date',
                placeholder='Market date...',
                multi=multi,
            ),
            html.Button(
                id='input-mkt-clear',
                children='clear',
            )
        ])


def query_status():
    # query text status
    return html.Div(id='market-query-status')


def table():
    # DB market browser
    return dash_table.DataTable(
        id='table-market-db',
        columns=[
            {
                "name": v,
                "id": k,
            } for k, v in (
                    dict(config['TABLECOLS']) | {'market_profit': 'Profit'}
            ).items()
        ],
        style_table={
            # 'height': '300px',
        },
        style_cell={
            'textAlign': 'left',
            'whiteSpace': 'normal',
            'height': 'auto',
            'textOverflow': 'ellipsis',
        },
        page_size=int(config['TABLE']['page_size']),
        sort_action="native",
    )

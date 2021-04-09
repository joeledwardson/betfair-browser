from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from ..config import config
from myutils.mydash import intermediate
from .defs import FILTER_MARGINS


def header():
    return dbc.Row([
        dbc.Col(
            html.H2('Market Browser'),
            width='auto'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-filter"),
                id="btn-db-filter",
                n_clicks=0
            ),
            width='auto',
            className='p-0'
        ),
        dbc.Col(),
        dbc.Col(
            dcc.Loading(
                html.Div(id='loading-out-db'),
                type='dot'
            ),
            className='anchor-right',
        )],
        align='center'
    )


def filters(multi):
    # market filters
    return [
        dcc.Dropdown(
            id='input-sport-type',
            placeholder='Sport...',
            className=FILTER_MARGINS
        ),
        dcc.Dropdown(
            id='input-mkt-type',
            placeholder='Market type...',
            multi=multi,
            className=FILTER_MARGINS
        ),
        dcc.Dropdown(
            id='input-bet-type',
            placeholder='Betting type...',
            multi=multi,
            className=FILTER_MARGINS
        ),
        dcc.Dropdown(
            id='input-format',
            placeholder='Format...',
            multi=multi,
            className=FILTER_MARGINS
        ),
        dcc.Dropdown(
            id='input-country-code',
            placeholder='Country...',
            multi=multi,
            optionHeight=60,
            className=FILTER_MARGINS
        ),
        dcc.Dropdown(
            id='input-venue',
            placeholder='Venue...',
            multi=multi,
            className=FILTER_MARGINS
        ),
        dcc.Dropdown(
            id='input-date',
            placeholder='Market date...',
            multi=multi,
            className=FILTER_MARGINS
        ),
        dbc.Button(
            id='input-mkt-clear',
            children='clear',
            className=FILTER_MARGINS
        )
    ]

    return html.Div(
        html.Div(
            opts,
            className='d-flex flex-column pr-2'
        ),
        className='flex-row flex-grow-1 y-scroll'
    )


def query_status():
    # query text status
    return dbc.Row(dbc.Col(
        html.Div(id='market-query-status')
    ))


def table():
    # DB market browser
    return dbc.Row(dbc.Col(
        dash_table.DataTable(
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
            sort_action="native"
        )
    ))

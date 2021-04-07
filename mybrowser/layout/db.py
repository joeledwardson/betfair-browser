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
    return html.Div([
        html.H2('Market Browser'),
        html.Div(dbc.Button(
            html.I(className="fas fa-filter"),
            id="btn-db-filter",
            n_clicks=0,
        )),
        html.Div(), # pad extra div to match grid title-container 4-column class
        html.Div(
            dcc.Loading(
                html.Div(id='loading-out-db'),
                type='dot'
            ),
            className='loading-container',
        )],
        className='title-container'
    )


def filters(multi):
    # market filters
    return html.Div(
        className='filters-container',
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
            dbc.Button(
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

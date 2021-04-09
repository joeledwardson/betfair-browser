from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from myutils import mytiming
from ..config import config
from ..tables.runners import get_runners_table, create_table
from myutils.mydash import intermediate


def header():
    # runner information header and loading bar
    return html.Div([
        html.H2('Runner info'),

        dbc.Button(
            html.I(className="fas fa-bars"),
            id="btn-runners-filter",
            n_clicks=0
        ),
        dbc.Button(
            children=html.I(className="fas fa-download"),
            id='button-runners',
            n_clicks=0,
            # color='primary',
            # style=input_styles
        ),

        html.Div(
            dcc.Loading(
                html.Div(id='loading-out-runners'),
                type='dot',
            ),
            className='loading-container',
        )],
        className='title-container'
    )


def filters():
    return html.Div([

    ])


def inputs(input_styles, chart_offset):
    # market/runner buttons
    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Button(
                ['Orders', html.I(className='fas fa-file-invoice-dollar ml-2')],
                id='button-orders',
                className='mr-1',
            ), width='auto'),
            dbc.Col(dbc.Button(
                ['Figure', html.I(className="fas fa-chart-line ml-2")],
                id='button-figure',
                className='mr-1',
            ), width='auto'),
            dbc.Col(dbc.Button(
                ['Timings', html.I(className='fas fa-hourglass ml-2')],
                id='button-timings',
                className='mr-1',
            ), width='auto'),
            dbc.Col(dcc.Loading(
                html.Div(id='loading-out-figure'),
                type='dot',
            )),
        ], no_gutters=True, align='center'),
        html.Div([
            html.Button(
                children='all feature figures',
                id='button-all-figures',
                n_clicks=0,
                style=input_styles
            ),

            dcc.Checklist(
                id='checklist-timings',
                options=[
                    {'label': 'timings', 'value': 'timings'},
                ],
                value=['timings'],
                labelStyle={'display': 'inline-block'},
                style={
                    'display': 'inline',
                    'margin': '3px 0px',
                },
            )
        ])

        # html.Button(
        #     children='reload libraries',
        #     id='button-libs',
        #     n_clicks=0,
        #     style=input_styles
        # ),
    ])


def market_info():
    # information about market
    return html.Div(children=[], id='infobox-market')


def table(height):
    """
    get empty mydash DataTable for runner information
    """
    return dash_table.DataTable(
        id='table-runners',
        columns=[{
            'name': v, 'id': v
        } for v in [
            'Selection ID',
            'Name',
            'Starting Odds',
            'Profit',
        ]],
        style_cell={
            'textAlign': 'left',
        },
        page_size=int(height),
        sort_action='native',
    )

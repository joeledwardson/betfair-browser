from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_table
import pandas as pd
from myutils import mytiming
from ..config import config
from ..tables.runners import get_runners_table, create_table
from myutils.mydash import intermediate


def header():
    # runner information header
    return html.H2(
        children='Runner info'
    )


def inputs(input_styles, chart_offset):
    # market/runner buttons
    return html.Div(
        children=[
            html.Button(
                children='get runners',
                id='button-runners',
                n_clicks=0,
                style=input_styles
            ),
            html.Button(
                children='order profits',
                id='button-orders',
                n_clicks=0,
                style=input_styles
            ),
            dcc.Input(
                id='input-chart-offset',
                type='time',
                value=mytiming.format_timedelta(chart_offset),
                style=input_styles
            ),
            html.Button(
                children='feature figure',
                id='button-figure',
                n_clicks=0,
                style=input_styles
            ),
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
            ),
            html.Button(
                children='reload feature configs',
                id='button-feature-config',
                n_clicks=0,
                style=input_styles
            ),
            html.Button(
                children='reload libraries',
                id='button-libs',
                n_clicks=0,
                style=input_styles
            ),
        ]
    )


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
        page_size=int(config['TABLE']['page_size']),
        sort_action='native',
    )
    # create_table(
    #     table_id='table-runners',
    #     df=pd.DataFrame({
    #         'Selection ID': [],
    #         'Name': [],
    #         'Starting Odds': [],
    #         'Profit': [],
    #     }),
    #     height=height,
    # )

from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
from myutils.timing import format_timedelta
from mytrading.browser.tables.runners import get_runners_table, get_runner_id
from mytrading.browser.tables.market import get_market_table
from mytrading.browser.tables.files import get_files_table, get_table_market
from mytrading.browser.tables.orders import get_orders_table
from mytrading.browser.data import DashData


def get_layout(input_dir: str, dash_data: DashData, chart_offset: timedelta):
    return html.Div(
        style={
            'display': 'grid',
            'grid-template-columns': '50% 50%'
        },
        children=[
            html.Div(
                style={
                    'margin': 10,
                },
                children=[
                    html.H1(
                        children='Betfair Browser'
                    ),

                    html.H2(
                        children='File Selection'
                    ),

                    html.Div(
                        id='infobox-files-cell',
                        children='',
                    ),

                    html.Div(
                        id='infobox-path',
                        children='',
                    ),

                    html.Div(
                        children=[
                            html.Button(children='↑', id='button-return', n_clicks=0),
                            html.Button(children='get runners', id='button-runners', n_clicks=0),
                            html.Button(children='profit', id='button-profit', n_clicks=0)
                        ],
                    ),

                    html.Div(
                        id='table-files-container',
                        children=get_files_table(dash_data.file_tracker, input_dir),
                        style={
                            'width': 'fit-content',
                        },
                    ),

                    html.H2(
                        children='Runner info'
                    ),

                    html.Div(
                        id='infobox-runners',
                        children='',
                    ),

                    html.Div(
                        children=[
                            html.Button(children='order profits', id='button-orders', n_clicks=0),
                            dcc.Input(id='input-chart-offset', type='time', value=format_timedelta(chart_offset)),
                            html.Button(children='feature figure', id='button-figure', n_clicks=0),
                        ]
                    ),

                    html.Div(
                        children=get_runners_table(),
                    ),

                ]
            ),

            html.Div(
                style={
                    'margin': 10,
                },
                children=[
                    html.H2(
                        children='Event Information'
                    ),

                    html.Div(
                        children=get_market_table()
                    ),

                    html.H2(
                        children='Figure information'
                    ),

                    html.Div(
                        id='infobox-figure',
                        children='',
                    ),

                    html.H2(
                        children='Order Profits'
                    ),

                    html.Div(
                        id='infobox-orders',
                        children='',
                    ),

                    html.Div(
                        children=get_orders_table(),
                    ),

                ]
            ),
        ],
    )
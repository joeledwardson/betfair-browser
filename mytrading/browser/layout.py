import dash_html_components as html
from mytrading.browser.tables.runners import get_runners_table, get_runner_id
from mytrading.browser.tables.market import get_market_table
from mytrading.browser.tables.files import get_files_table, get_table_market
from mytrading.browser.data import DashData


def get_layout(input_dir: str, dash_data: DashData):
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
                        id='active-cell-display',
                        children='',
                    ),

                    html.Div(
                        id='path-display',
                        children='',
                    ),

                    html.Div(
                        children=[
                            html.Button(children='↑', id='return-button', n_clicks=0),
                            html.Button(children='get runners', id='runners-button', n_clicks=0),
                            html.Button(children='feature figure', id='fig-button', n_clicks=0),
                            html.Button(children='profit', id='profit-button', n_clicks=0)
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
                        id='file-info',
                        children='',
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
                    html.H2(children='Event Information'),

                    html.Div(
                        children=get_market_table()
                    ),

                    html.H2(children='Figure information'),

                    html.Div(
                        id='figure-info',
                        children='',
                    )
                ]
            ),
        ]
    )
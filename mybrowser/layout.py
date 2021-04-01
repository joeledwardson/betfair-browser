from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_table
import pandas as pd

from .tables.runners import get_runners_table
from .tables.files import get_files_table, FilesTableProperties
from .tables.orders import get_orders_table
from .tables.table import create_table
from .callbacks import db
from .data import DashData
from .config import config
from myutils.mydash import intermediate
from myutils import mytiming


# set files table height as it is needed when re-created in callbacks
FilesTableProperties.height = '20vh'

input_styles = {
    'margin': '3px 2px',
}


def infobox(height=70, **kwargs) -> html.Div:
    return html.Div(
        style={
            'height': height,
            'overflow-y': 'auto',
        },
        **kwargs,
    )


multi = False


def get_layout(
        input_dir: str,
        dash_data: DashData,
        chart_offset: timedelta,
        feature_config_initial: Optional[str] = None,
        plot_config_initial: Optional[str] = None,
) -> html.Div:
    # container
    return html.Div(
        style={
            'display': 'grid',
            'grid-template-columns': '50% 50%',
            'height': '100vh',
            'position': 'relative',
        },
        children=[
            intermediate.hidden_div('intermediary-market'),
            intermediate.hidden_div('intermediary-featureconfigs'),
            intermediate.hidden_div('intermediary-figure'),
            intermediate.hidden_div('intermediary-libs'),
            intermediate.hidden_div('intermediary-orders'),
            intermediate.hidden_div('intermediary-files'),
            intermediate.hidden_div('intermediary-mkt-type'),

            # left column container
            html.Div(
                style={
                    'margin': '10px 25px',
                },
                children=[
                    html.H1(
                        children='Betfair Browser'
                    ),

                    html.H2(
                        children='File Selection'
                    ),

                    html.Div(
                        children=[
                            html.Button(children='↑', id='button-return', n_clicks=0, style=input_styles),
                            html.Button(children='get runners', id='button-runners', n_clicks=0, style=input_styles),
                            html.Button(children='profit', id='button-profit', n_clicks=0, style=input_styles),
                        ],
                    ),

                    # market filters
                    html.Div(
                        style={
                            'margin': '10px 0px',
                            'width': '50%',
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
                    ]),

                    # strategy filters
                    html.Div(
                        style={
                            'margin': '10px 0px',
                            'width': '50%',
                            'display': 'grid',
                            'grid-template-columns': '1fr 1fr',
                            'grid-row-gap': '2px',
                            'grid-column-gap': '8px',
                        },
                        children=[
                            dcc.Dropdown(
                                id='input-strategy-select',
                                placeholder='Strategy...'
                            ),
                            html.Button(
                                id='input-strategy-clear',
                                children='clear',
                            ),
                        ],
                    ),

                    # query text status
                    html.Div(id='market-query-status'),

                    # DB market browser
                    dash_table.DataTable(
                        id='table-market-db',
                        columns=[{
                            "name": v,
                            "id": k,
                        } for k, v in config['TABLECOLS'].items()],
                        style_table={
                            # 'height': '300px',
                        },
                        style_cell={
                            'textAlign': 'left',
                            'maxWidth': 0,
                        },
                        page_size=int(config['TABLE']['page_size']),
                        sort_action="native",
                    ),

                    # html.P(id='infobox-files', children='', style={'margin': 0}),
                    #
                    # html.Div(
                    #     id='table-files-container',
                    #     children=get_files_table(dash_data.file_tracker, input_dir),
                    #     style={
                    #         'width': 'fit-content',
                    #     },
                    # ),

                    html.H2(
                        children='Runner info'
                    ),

                    html.Div(
                        children=[
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
                    ),

                    html.Div(
                        children=[
                            html.Div(
                                style={
                                    'display': 'grid',
                                    'grid-template-columns': 'auto auto',
                                    'grid-row-gap': '2px',
                                    'grid-column-gap': '8px',
                                },
                                children=[
                                    dcc.Dropdown(
                                        id='input-feature-config',
                                        placeholder='Select feature config',
                                        # style={
                                        #     'margin': '4px 2px'
                                        # },
                                        value=feature_config_initial,
                                    ),
                                    dcc.Dropdown(
                                        id='input-plot-config',
                                        placeholder='Select plot config',
                                        # style={
                                        #     'margin': '4px 2px'
                                        # },
                                        value=plot_config_initial,
                                    ),
                                ]
                            )
                        ],
                    ),

                    html.Div(children=[], id='infobox-market'),

                    html.Div(
                        children=get_runners_table(height=200),
                    ),

                ]
            ),

            # right column container
            html.Div(
                style={
                    'margin': '10px 25px',
                },
                children=[


                    html.H2(
                        children='Order Profits'
                    ),

                    html.Div(
                        children=get_orders_table(height=340),
                    ),

                    html.H2(
                        children='Function Timings',
                    ),

                    html.Div(
                        children=create_table(
                            table_id='table-timings',
                            df=pd.DataFrame(columns=[
                                'Function',
                                'Count',
                                'Mean',
                            ]),
                            height=340,
                        ),
                    )

                ]
            ),

            # bottom logging box
            html.Div(
                id='logger-box',
                # use display flex and reverse div row order so first in list appears at bottom, so that scroll bar
                # stays at bottom
                style={
                    'display': 'flex',
                    'flex-direction': 'column-reverse',
                    'overflow-y': 'scroll',
                    'grid-column-start': '1',
                    'grid-column-end': '3',
                    'background-color': 'lightgrey',
                    'height': 170,
                    'align-self': 'end',
                    'margin': 5,
                },
                children=[],
            )
        ],
    )
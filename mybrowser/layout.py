from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
from .tables.runners import get_runners_table, get_runner_id
from .tables.market import get_market_table
from .tables.files import get_files_table, FilesTableProperties
from .tables.orders import get_orders_table
from .data import DashData

from myutils import timing as mytiming

# set files table height as it is needed when re-created in callbacks
FilesTableProperties.height = 200


def infobox(height=70, **kwargs) -> html.Div:
    return html.Div(
        style={
            'height': height,
            'overflow-y': 'auto',
        },
        **kwargs,
    )


def hidden_div(div_id) -> html.Div:
    return html.Div(
        children='',
        style={'display': 'none'},
        id=div_id,
    )


def get_layout(
        input_dir: str,
        dash_data: DashData,
        chart_offset: timedelta,
        initial_feature_conf: Optional[str] = None,
        initial_plot_conf: Optional[str] = None,
) -> html.Div:
    return html.Div(
        style={
            'display': 'grid',
            'grid-template-columns': '50% 50%',
        },
        children=[
            hidden_div('intermediary-market'),
            hidden_div('intermediary-featureconfigs'),
            hidden_div('intermediary-figure'),
            hidden_div('intermediary-libs'),
            hidden_div('intermediary-orders'),
            hidden_div('intermediary-files'),
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
                        children=[
                            html.Button(children='↑', id='button-return', n_clicks=0),
                            html.Button(children='get runners', id='button-runners', n_clicks=0),
                            html.Button(children='profit', id='button-profit', n_clicks=0),
                            html.Button(children='reload libraries', id='button-libs', n_clicks=0),
                        ],
                    ),

                    html.P(id='infobox-files', children='', style={'margin': 0}),

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
                        children=[
                            html.Button(children='order profits', id='button-orders', n_clicks=0),
                            dcc.Input(id='input-chart-offset', type='time', value=mytiming.format_timedelta(chart_offset)),
                            html.Button(children='feature figure', id='button-figure', n_clicks=0),
                        ]
                    ),

                    html.Div(
                        children=get_runners_table(height=200),
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
                        children=get_market_table(height=140, width=600)
                    ),

                    html.H2(
                        children='Feature Config Selection'
                    ),

                    html.Div(
                        children=[
                            html.Button(
                                children='reload feature configs',
                                id='button-feature-config',
                                n_clicks=0
                            ),
                            html.Div(
                                style={
                                    'display': 'grid',
                                    'grid-template-columns': '50% 50%'
                                },
                                children=[
                                    dcc.Dropdown(
                                        id='input-feature-config',
                                        placeholder='Select feature config',
                                        style={
                                            'margin': '4px 0px'
                                        },
                                        value=initial_feature_conf,
                                    ),
                                    dcc.Dropdown(
                                        id='input-plot-config',
                                        placeholder='Select plot config',
                                        style={
                                            'margin': '4px 0px'
                                        },
                                        value=initial_plot_conf,
                                    ),
                                ]
                            )
                        ],
                    ),

                    html.H2(
                        children='Order Profits'
                    ),

                    html.Div(
                        children=get_orders_table(height=340),
                    ),

                ]
            ),

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
                    'height': 130,
                },
                children=[],
            )
        ],
    )
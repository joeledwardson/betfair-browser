from typing import Optional
from datetime import timedelta
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
from ..data import DashData
from .. import callbacks
from . import db, strategy, runners, configs, orders, timings, logging
from myutils.mydash import intermediate
from myutils import mytiming


# set files table height as it is needed when re-created in callbacks
# FilesTableProperties.height = '20vh'

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



col_style = {
    'padding': '10px 25px',
    'position': 'relative',
}


# TODO - put CSS into own file, easier than keeping it here
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

            html.Div(
                children=[
                    html.H1(
                        children='Betfair Browser',
                        style={
                            'margin': '2px'
                        }
                    ),

                    dbc.Button(
                        [
                            html.I(className="fas fa-envelope-open-text mr-2"),
                            html.Span("Messages"),
                        ],
                        id="open",
                        style={
                            'position': 'absolute',
                            'justify-self': 'end',
                            'margin': '3px',
                        }
                    ),
                ],
                style={
                    'grid-column': 'span 2',
                    'display': 'grid',
                    'position': 'relative',
                    'justify-content': 'center',
                    'align-items': 'center',
                    'background-color': '#f5aa5b',
                }
            ),

            dbc.Modal(
                [
                    dbc.ModalHeader("Log"),
                    dbc.ModalBody(logging.log_box()),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="close", className="ml-auto")
                    ),
                ],
                id="modal",
                size='xl',
            ),

            # hidden divs for intermediary output components
            *[
                intermediate.hidden_div(o.component_id)
                for o in callbacks.IORegister.outs_reg
            ],

            # periodic update
            dcc.Interval(
                id='interval-component',
                interval=1 * 1000,  # in milliseconds
                n_intervals=0
            ),

            # left column container
            html.Div(
                style=col_style,
                children=[

                    # filter bar
                    html.Div(
                        id='side-bar',
                        children=[
                            html.H2('filters'),
                            html.Hr(),
                            dbc.Button('close', id='btn-side-bar'),
                        ],
                        style={
                            'left': '0',
                            'top': '0',
                            'height': '100%',
                            'position': 'absolute',
                            'width': '30rem',
                            'margin-left': '-30rem',
                            'margin-top': '0',
                            'margin-bottom': '0',
                            'background': 'lightblue',
                            'transition': 'margin-left 0.4s ease-in-out 0.1s',
                            'z-index': '1',
                            'padding': '10px',
                        },
                    ),

                    # TODO add grid here for percentage based rows for market and runner tables - after that can
                    #  remove table padding to maintain fixed spage on page
                    db.header(),
                    db.filters(multi=False),
                    strategy.filters(),
                    db.query_status(),
                    db.table(),

                    html.Br(),

                    runners.header(),
                    runners.inputs(input_styles, chart_offset),
                    configs.inputs(feature_config_initial, plot_config_initial),
                    runners.market_info(),
                    # TODO update page size from config
                    runners.table(8),
                ]
            ),

            # right column container
            html.Div(
                style=col_style | {'position': 'relative'},
                children=html.Div(
                    style={
                        'height': '100%',
                        'display': 'grid',
                        'grid-template-rows': '50% 50%',
                    },
                    children=[
                        # TODO move orders and timings into popups
                        html.Div(children=[
                            orders.header(),
                            orders.table(340),
                        ]),
                        html.Div(children=[
                            timings.header(),
                            timings.table(),
                        ])
                    ]
                )
            ),

            # TODO - make logging box popup and have different colours for messages
            # log box
            # logging.log_box(),
        ],
    )

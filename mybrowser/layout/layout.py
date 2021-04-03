from typing import Optional
from datetime import timedelta
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


# TODO make layout into different functions that are called

col_style = {
    'margin': '10px 25px',
}


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
                    html.H1(children='Betfair Browser'),

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

            # log box
            logging.log_box(),
        ],
    )

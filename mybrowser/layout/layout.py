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

def hidden_elements():

    return [

        dbc.Modal(
            id="modal",
            size='xl',
            children=[
                dbc.ModalHeader("Log"),
                dbc.ModalBody(logging.log_box()),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close", className="ml-auto")
                ),
            ],
        ),

        dbc.Modal([
            dbc.ModalHeader('Libraries reloaded'),
            dbc.ModalFooter(
                dbc.Button(
                    "Close",
                    id="modal-close-libs",
                    className='ml-auto'
                )
            )],
            id='modal-libs',
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
        )
    ]


def header():
    return html.Div([
        html.H1('Betfair Browser'),
        html.Div([
            html.Div(dcc.Loading(
                type='dot',
                children=html.Div(id='loading-out-header'),
            ),
                id='header-loading-container',
                className='loading-container',
            ),
            dbc.Button(
                id='button-libs',
                children=html.I(className="fas fa-book-open"),
            ),
            dbc.Button(
                id='open',
                children=html.I(className="fas fa-envelope-open-text"),
            )],
            id='header-bar'
        )],
        id='header-container'
    )


def left_col(feature_config_initial, plot_config_initial):
    # left column container
    return html.Div([

        # filter bar
        html.Div([
            html.Div([
                html.H2('Plot Config'),
                dbc.Button('close', id='btn-left-close')],
                className='sidebar-title'
            ),
            html.Hr(),
            configs.inputs(feature_config_initial, plot_config_initial)],
            id='left-side-bar'
        ),

        # TODO add grid here for percentage based rows for market and runner tables - after that can
        #  remove table padding to maintain fixed spage on page
        db.header(),
        db.query_status(),
        db.table()],
        className='col-container'
    )


def right_col(chart_offset, feature_config_initial, plot_config_initial):
    # right column container
    return html.Div([
        # filter bar
        html.Div([
            html.Div([
                html.H2('Market Filters'),
                dbc.Button('close', id='btn-right-close')],
                className='sidebar-title'
            ),
            html.Hr(),
            db.filters(multi=False),
            html.Hr(),
            strategy.filters(),
            html.Hr()],
            id='right-side-bar',
        ),

        runners.header(),
        runners.inputs(input_styles, chart_offset),
        runners.market_info(),
        # TODO update page size from config
        runners.table(8),

        # TODO move orders and timings into popups
        html.Div(children=[
            orders.header(),
            orders.table(340),
        ]),
        html.Div(children=[
            timings.header(),
            timings.table(),
        ])],
        className='col-container'
    )


# TODO - put CSS into own file, easier than keeping it here
def get_layout(
        input_dir: str,
        dash_data: DashData,
        chart_offset: timedelta,
        feature_config_initial: Optional[str] = None,
        plot_config_initial: Optional[str] = None,
) -> html.Div:
    # container
    return html.Div([
        *hidden_elements(),
        html.Div(
            id='bf-container',
            children=[
                header(),
                left_col(feature_config_initial, plot_config_initial),
                right_col(chart_offset, feature_config_initial, plot_config_initial)
            ]
        )
    ])

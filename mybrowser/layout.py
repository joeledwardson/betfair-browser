from typing import Optional
from datetime import timedelta
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc

from myutils.mydash import intermediate

from .data import DashData
from . import callbacks
from .layouts import db, strategy, runners, configs, orders, timings, logging
from .intermeds import INTERMEDIARIES


def hidden_elements():
    return [

        dbc.Modal([
            dbc.ModalHeader("Orders"),
            dbc.ModalBody(orders.table()),
            dbc.ModalFooter(
                dbc.Button("Close", id="modal-close-orders", className="ml-auto")
            )],
            id="modal-orders",
            size="xl"
        ),

        dbc.Modal([
            dbc.ModalHeader('Timings'),
            dbc.ModalBody(timings.table()),
            dbc.ModalFooter(
                dbc.Button('Close', id='modal-close-timings', className='ml-auto')
            )],
            id='modal-timings',
            size='xl'
        ),

        dbc.Modal([
            dbc.ModalHeader("Log"),
            dbc.ModalBody(logging.log_box()),
            dbc.ModalFooter(
                dbc.Button("Close", id="modal-close-log", className="ml-auto")
            )],
            id="modal-logs",
            size='xl',
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
        *[intermediate.hidden_div(x) for x in INTERMEDIARIES],

        # periodic update
        dcc.Interval(
            id='interval-component',
            interval=1 * 1000,  # in milliseconds
            n_intervals=0
        )
    ]


def header():

    end = dbc.Row([
        dbc.Col(
            dcc.Loading(
                type='dot',
                children=html.Div(id='loading-out-header')
            )
        ),
        dbc.Col(
            dbc.Button(
                id='button-libs',
                children=html.I(className="fas fa-book-open")
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                id='button-log',
                children=html.I(className="fas fa-envelope-open-text")
            ),
            width='auto',
            className='p-1'
        )],
        align='center',
        no_gutters=True,
    )

    return dbc.Row([
        dbc.Col(
            width=3
        ),
        dbc.Col(
            dbc.Row(
                dbc.Col(html.H1('Betfair Browser'), width='auto'),
                justify='center',
                align='center'
            ),
            width=6,
        ),
        dbc.Col(
            end,
            width=3
        )],
        align='center',
        className='bg-light'
    )


def left_col(feature_config_initial, plot_config_initial):

    filter_bar = html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Plot Config')),
                    dbc.Col(dbc.Button('close', id='btn-left-close'), width='auto')],
                    align='center',
                ),
                html.Hr(className='ml-0 mr-0'),
                configs.inputs(feature_config_initial, plot_config_initial)
            ],
            className='d-flex flex-column h-100 p-3'
        ),
        id='left-side-bar'
    )

    # left column container
    return dbc.Col([

        # filter bar
        filter_bar,

        # TODO add grid here for percentage based rows for market and runner tables - after that can
        #  remove table padding to maintain fixed spage on page

        html.Div([
            db.header(),
            db.query_status(),
            db.table()
        ], className='shadow h-100 p-4')],
        width=6,
        className='p-4'
    )


def right_col():

    filter_bar = html.Div(
        html.Div([
            dbc.Row([
                dbc.Col(html.H2('Market Filters')),
                dbc.Col(dbc.Button('close', id='btn-right-close'), width='auto')],
                align='center'
            ),
            html.Hr(className='ml-0 mr-0'),
            html.Div(
                [
                    *db.filters(multi=False),
                    html.Hr(className='ml-0 mr-0'),
                    *strategy.filters()
                ],
                className='d-flex flex-column pr-2'
            )],
            className='d-flex flex-column h-100 p-3'
        ),
        id='right-side-bar'
    )

    # right column container
    return dbc.Col([
        # filter bar
        filter_bar,

        html.Div([
            runners.header(),
            runners.inputs(),
            runners.market_info(),
            runners.table()
        ], className='shadow h-100 p-4')],
        width=6,
        className='p-4'
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
        header(),
        dbc.Row([
            left_col(feature_config_initial, plot_config_initial),
            right_col()
        ], no_gutters=True, className='flex-row flex-grow-1')],
        id='bf-container',
        className='d-flex flex-column'
    )

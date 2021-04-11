from typing import Optional
from datetime import timedelta
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc

from myutils.mydash import intermediate

from .data import DashData
from . import callbacks
from .layouts import market, strategy, runners, configs, orders, timings, logger
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
            dbc.ModalBody(logger.log_box()),
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
                html.Div(id='loading-out-header'),
                type='dot'
            )
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-book-open"),
                id='button-libs',
                color='info'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            # TODO - add labels for errors/warnings
            dbc.Button(
                html.I(className="fas fa-envelope-open-text"),
                id='button-log',
                color='info'
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


def left_col():

    filter_bar = html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Plot Config')),
                    dbc.Col(dbc.Button('close', id='btn-left-close'), width='auto')],
                    align='center',
                ),
                html.Hr(className='ml-0 mr-0'),
                configs.inputs()
            ],
            className='d-flex flex-column h-100 p-3'
        ),
        id='left-side-bar'
    )

    # left column container
    return dbc.Col([

        # filter bar
        filter_bar,

        html.Div([
            market.header(),
            market.query_status(),
            market.table()
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
                    *market.filters(multi=False),
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


def get_layout() -> html.Div:
    # container
    return html.Div([
        *hidden_elements(),
        header(),
        dbc.Row([
            left_col(),
            right_col()
        ], no_gutters=True, className='flex-row flex-grow-1')],
        id='bf-container',
        className='d-flex flex-column'
    )

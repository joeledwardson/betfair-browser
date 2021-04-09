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

        dbc.Modal([
            dbc.ModalHeader("Orders"),
            dbc.ModalBody(orders.table(340)),
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
    return dbc.Row([
        dbc.Col(width=3),
        dbc.Col(
            dbc.Row(
                dbc.Col(html.H1('Betfair Browser'), width='auto'),
                justify='center',
                align='center'
            ),
            width=6,
        ),
        dbc.Col(
            dbc.Row([
                dbc.Col(dcc.Loading(
                    type='dot',
                    children=html.Div(id='loading-out-header'),
                )),
                dbc.Col(dbc.Button(
                    id='button-libs',
                    children=html.I(className="fas fa-book-open"),
                ), width='auto'),
                dbc.Col(dbc.Button(
                    id='open',
                    children=html.I(className="fas fa-envelope-open-text"),
                ), width='auto')],
                align='center',
                no_gutters=True,
            ),
            width=3
        )],
        align='center',
        className='bg-light'
        # style={
        #     'grid-column': 'span 2'
        # }
    )
    # return html.Div([
    #     html.H1('Betfair Browser'),
    #     html.Div([
    #         html.Div(dcc.Loading(
    #             type='dot',
    #             children=html.Div(id='loading-out-header'),
    #         ),
    #             id='header-loading-container',
    #             className='loading-container',
    #         ),
    #         dbc.Button(
    #             id='button-libs',
    #             children=html.I(className="fas fa-book-open"),
    #         ),
    #         dbc.Button(
    #             id='open',
    #             children=html.I(className="fas fa-envelope-open-text"),
    #         )],
    #         id='header-bar'
    #     )],
    #     id='header-container'
    # )


def left_col(feature_config_initial, plot_config_initial):
    # left column container
    return dbc.Col([

        # filter bar
        html.Div(
            html.Div(
                [
                    dbc.Row([
                        dbc.Col(html.H2('Plot Config')),
                        dbc.Col(dbc.Button('close', id='btn-left-close'), width='auto')],
                        align='center',
                    ),
                    html.Hr(),
                    configs.inputs(feature_config_initial, plot_config_initial)
                ],
                className='d-flex flex-column h-100 p-3'
            ),
            id='left-side-bar'
        ),

        # TODO add grid here for percentage based rows for market and runner tables - after that can
        #  remove table padding to maintain fixed spage on page
        db.header(),
        db.query_status(),
        db.table()],
        width=6,
        className='p-4'
        # className='col-container'
    )


def right_col(chart_offset, feature_config_initial, plot_config_initial):
    # right column container
    return dbc.Col([
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
        runners.table(8)],
        width=6,
        className='p-4'
        # className='col-container'
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
            right_col(chart_offset, feature_config_initial, plot_config_initial)
        ], no_gutters=True, className='flex-row flex-grow-1')],
        id='bf-container',
        className='d-flex flex-column'
    )

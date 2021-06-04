import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc

import myutils.mydash

from .layouts import market, runners, configs, orders, timings, logger, INTERMEDIARIES

# TODO - sidebar nav which expands on hover - make sidebars come in from the right but positioned on page
class ToastHandler:

    top = 50

    @classmethod
    def get_toast(cls, toast_id, header, icon='info'):
        # cls.top += 20
        return dbc.Toast(
            id=toast_id,
            header=header,
            is_open=False,
            dismissable=True,
            icon=icon,
            duration=360000,
            style={
                "position": "fixed",
                "top": cls.top,
                "right": 50,
                # "width": 350
            },
        )


def hidden_elements(n_odr_rows, n_tmr_rows):
    return [

        dbc.Modal([
            dbc.ModalHeader("Orders"),
            dbc.ModalBody(orders.table(n_odr_rows)),
            dbc.ModalFooter(
                dbc.Button("Close", id="modal-close-orders", className="ml-auto")
            )],
            id="modal-orders",
            size="xl"
        ),

        # dbc.Modal([
        #     dbc.ModalHeader('Timings'),
        #     dbc.ModalBody(timings.table(n_tmr_rows)),
        #     dbc.ModalFooter(
        #         dbc.Button('Close', id='modal-close-timings', className='ml-auto')
        #     )],
        #     id='modal-timings',
        #     size='xl'
        # ),

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


        dbc.Modal([
            dbc.ModalHeader('Feature/plot configurations reloaded'),
            dbc.ModalFooter(
                dbc.Button(
                    "Close",
                    id="modal-close-fcfgs",
                    className='ml-auto'
                )
            )],
            id='modal-fcfgs',
        ),

        # hidden divs for intermediary output components
        *[myutils.mydash.hidden_div(x) for x in INTERMEDIARIES],

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
        dbc.Col([
            dbc.Button(
                html.I(className="fas fa-envelope-open-text"),
                id='button-log',
                color='info'
            ),
            html.Div(
                dbc.Badge(id='log-warns', color="danger", className='p-2'),
                id='msg-alert-box',
                className='right-corner-box',
                hidden=True
            )],
            width='auto',
            className='p-1'
        )],
        align='center',
        no_gutters=True,
    )

    return dbc.Row([
        dbc.Col(
            html.Div(
                dbc.Progress(
                    id='header-progress-bar',
                    striped=True,
                    animated=True,
                ),
                id='progress-container-div',
                hidden=True,
            ),
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
        className='bg-light py-2 px-4'
    )


def plot_filter_div(filter_margins, dflt_offset):
    return html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Plot Config')),
                    dbc.Col(dbc.Button('close', id='btn-left-close'), width='auto')],
                    align='center',
                ),
                html.Hr(className='ml-0 mr-0'),
                configs.inputs(filter_margins, dflt_offset)
            ],
            className='d-flex flex-column h-100 p-3'
        ),
        className='right-side-bar',
        id='container-filters-plot'
    )


def market_div(mkt_tbl_cols, n_mkt_rows):
    return html.Div([
        html.Div(id='mkt-pls'),
        market.header(),
        market.mkt_buttons(),
        market.query_status(),
        market.mkt_table(mkt_tbl_cols, n_mkt_rows)
    ], className='flex-grow-1 shadow m-4 p-2', id='container-market')


def market_filter_div(filter_margins):
    return html.Div(
        html.Div([
            dbc.Row([
                dbc.Col(html.H2('Market Filters')),
                dbc.Col(dbc.Button('close', id='btn-right-close'), width='auto')],
                align='center'
            ),
            html.Hr(className='ml-0 mr-0'),
            html.Div(
                [
                    *market.mkt_filters(multi=False, filter_margins=filter_margins),
                    html.Hr(className='ml-0 mr-0'),
                    *market.strat_filters(filter_margins),
                    html.Hr(className='ml-0 mr-0'),
                    *market.strat_buttons(filter_margins)
                ],
                className='d-flex flex-column pr-2 overflow-auto'
            )],
            className='d-flex flex-column h-100 p-3'
        ),
        className='right-side-bar',
        id='container-filters-market'
    )


def runners_div(n_run_rows):
    return html.Div([
        runners.header(),
        runners.inputs(),
        runners.market_info(),
        runners.table(n_run_rows)
    ], className='flex-grow-1 p-3', id='container-runners')


def timings_div(n_tmr_rows):
    return html.Div(
        timings.table(n_tmr_rows),
        id='container-timings',
        className='shadow m-4 p-3 flex-grow-1'
    )


nav = html.Div([
    # html.I(className='fas fa-horse fa-lg'),
    # html.Hr(),
    dbc.Nav(
        [
            dbc.NavLink(
                [
                    html.I(className="fas fa-horse"),
                    html.Span("")
                ],
                href="/",
                active="exact",
            ),
            dbc.NavLink(
                [
                    html.I(className="fas fa-chess-king"),
                    html.Span(""),
                ],
                href="/strategy",
                active="exact",
            ),
            dbc.NavLink(
                [
                    html.I(className="fas fa-running"),
                    html.Span(""),
                ],
                href="/runners",
                active="exact",
            ),
            dbc.NavLink(
                [
                    html.I(className="fas fa-clock"),
                    html.Span(""),
                ],
                href="/timings",
                active="exact",
            ),
        ],
        vertical=True,
        pills=True,
        className='align-items-center h-100 pt-2'
    )
], id='nav-bar')


def get_layout(
        n_odr_rows,
        n_tmr_rows,
        filter_margins,
        dflt_offset,
        mkt_tbl_cols,
        n_mkt_rows,
        n_run_rows
) -> html.Div:
    # container
    return html.Div([
        dcc.Location(id="url"),
        html.Div(hidden_elements(n_odr_rows, n_tmr_rows)),
        html.Div(
            [
                header(),
                html.Div(
                    [
                        nav,
                        market_div(mkt_tbl_cols, n_mkt_rows),
                        runners_div(n_run_rows),
                        timings_div(n_tmr_rows),
                        market_filter_div(filter_margins),
                        plot_filter_div(filter_margins, dflt_offset),
                    ],
                    className='d-flex flex-row flex-grow-1 overflow-hidden'
                ),
                html.Div(id='toast-holder'),
            ],
            id='bf-container',
            className='d-flex flex-column'
        )
    ])

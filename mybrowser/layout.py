import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
import dash_table
import myutils.mydash
from .layouts import market, runners, configs, orders, timings, logger, INTERMEDIARIES


def strategy_modal():
    return dbc.Modal(
        [
            dbc.ModalHeader("Delete strategy?"),
            dbc.ModalFooter([
                dbc.Button("Yes", id="strategy-delete-yes", color='danger', className='ml-auto'),
                dbc.Button("No", id="strategy-delete-no", color='success')
            ]),
        ],
        id="strategy-delete-modal",
    )


# TODO - move all loading bars to top
def hidden_elements(n_odr_rows, n_tmr_rows):
    return [
        strategy_modal(),
        # TODO - make orders its own page
        dbc.Modal([
            dbc.ModalHeader("Orders"),
            dbc.ModalBody(orders.table(n_odr_rows)),
            dbc.ModalFooter(
                dbc.Button("Close", id="modal-close-orders", className="ml-auto")
            )],
            id="modal-orders",
            size="xl"
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
        dbc.Col([
            dcc.Loading(
                html.Div(id='loading-out-header'),
                type='dot'
            ),
            dcc.Loading(
                html.Div(id='loading-out-session'),
                type='dot'
            ),
        ]),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-book-open"),
                id='button-libs',
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


def market_div(mkt_tbl_cols, n_mkt_rows, market_sort_options):
    return html.Div(
        html.Div(
            [
                market.header(),
                market.mkt_buttons(market_sort_options),
                market.query_status(),
                market.mkt_table(mkt_tbl_cols, n_mkt_rows)
            ],
            className='d-flex flex-column h-100'
        ),
        className='flex-grow-1 shadow m-4 p-4',
        id='container-market'
    )


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
                ],
                className='d-flex flex-column pr-2 overflow-auto'
            )],
            className='d-flex flex-column h-100 p-3'
        ),
        className='right-side-bar',
        id='container-filters-market'
    )


def strat_filter_div(filter_margins):
    return html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Strategy Filters')),
                    dbc.Col(dbc.Button('close', id='btn-strategy-close'), width='auto'),
                ], align='center'),
                html.Hr(),
            ],
            className='d-flex flex-column h-100 p-3'
        ),
        className='right-side-bar',
        id='container-filters-strategy'
    )


def runners_div(n_run_rows):
    return html.Div([
        runners.header(),
        runners.inputs(),
        runners.market_info(),
        runners.table(n_run_rows)
    ], className='flex-grow-1 shadow m-4 p-4 overflow-auto', id='container-runners')


def timings_div(n_tmr_rows):
    return html.Div(
        [
            html.H2('Timings'),
            timings.table(n_tmr_rows)
        ],
        id='container-timings',
        className='shadow m-4 p-4 flex-grow-1 overflow-auto'
    )


def log_div():
    return html.Div(
        html.Div(
            [
                html.H2('Python Log'),
                logger.log_box()
            ],
            className='d-flex flex-column h-100'
        ),
        className='flex-grow-1 shadow m-4 p-4 overflow-auto',
        id='container-logs'
    )


def strat_div(n_strat_rows, strat_cols):
    full_strat_cols = strat_cols | {
        'n_markets': 'Market Count',
        'total_profit': 'Total Profit'
    }
    return html.Div(
        html.Div(
            [
                dbc.Row([
                    dbc.Col(html.H2('Strategies'), width='auto'),
                    dbc.Col(
                        dbc.Button(
                            html.I(className="fas fa-filter"),
                            id="btn-strategy-filter",
                            n_clicks=0,
                            color='primary'
                        ),
                        width='auto',
                        className='p-1'
                    ),
                    dbc.Col(
                        dbc.NavLink(
                            dbc.Button(
                                html.I(className="fas fa-download"),
                                id="btn-strategy-download",
                                n_clicks=0,
                                color='primary'
                            ),
                            href="/",
                            active="exact",
                            className='p-0',
                            id='nav-strategy-download',
                        ),
                        width='auto',
                        className='p-1'
                    )
                ], align='center'),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            ['Reload', html.I(className="fas fa-sync-alt ml-2")],
                            id="btn-strategy-refresh",
                            n_clicks=0,
                            color='primary'
                        ),
                        width='auto',
                        className='pr-1'
                    ),
                    dbc.Col(
                        dbc.Button(
                            ['Delete Strategy', html.I(className="fas fa-trash ml-2")],
                            id="btn-strategy-delete",
                            n_clicks=0,
                            color='danger'
                        ),
                        width='auto',
                        className='p-1'
                    ),
                ], align='center'),
                dbc.Row([
                    dbc.Col(
                        dbc.Select(
                            id='input-strategy-run',
                            placeholder='Strategy config...',
                        ),
                        width='auto',
                        className='pr-1'
                    ),
                    dbc.Col(
                        dbc.Button(
                            'Reload configs...',
                            id='btn-strategies-reload',
                            n_clicks=0,
                            color='info',
                        ),
                        width='auto',
                        className='p-1'
                    ),
                    dbc.Col(
                        dbc.Button(
                            ['Run Strategy', html.I(className="fas fa-play-circle ml-2")],
                            id="btn-strategy-run",
                            n_clicks=0,
                        ),
                        width='auto',
                        className='p-1'
                    ),
                ], align='center'),
                html.Div(
                    dash_table.DataTable(
                        id='table-strategies',
                        columns=[
                            {"name": v, "id": k}
                            for k, v in full_strat_cols.items()
                        ],
                        style_cell={
                            'textAlign': 'left',
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'maxWidth': 0,  # fix column widths
                            'verticalAlign': 'middle',
                            'padding': '0.5rem',
                        },
                        style_data={
                            'border': 'none'
                        },
                        css=[{
                            'selector': 'td.dash-cell',
                            'rule': 'overflow-wrap: anywhere;'
                        }],
                        style_header={
                            'fontWeight': 'bold',
                            'border': 'none'
                        },
                        # the width and height properties below are just placeholders
                        # when using fixed_rows with headers they cannot be relative or dash crashes - these are overridden in css
                        style_table={
                            'overflowY': 'auto',
                            # 'minHeight': '80vh', 'height': '80vh', 'maxHeight': '80vh',
                            # 'minWidth': '100vw', 'width': '100vw', 'maxWidth': '100vw'
                        },
                        # fixed_rows={
                        #     'headers': True,
                        #     'data': 0
                        # },
                        page_size=n_strat_rows,
                    ),
                    className='table-container flex-grow-1 overflow-hidden'
                )
            ],
            className='h-100 d-flex flex-column'
        ),
        className='flex-grow-1 shadow m-4 p-4 overflow-hidden',
        id='container-strategy'
    )


# TODO - add padding
nav = html.Div([
    dbc.Nav(
        [
            dbc.NavLink(
                [
                    html.I(className="fas fa-horse"),
                    html.Span("")
                ],
                href="/",
                active="exact",
                className='m-1'
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
            dbc.NavLink(
                [
                    html.I(className="fas fas fa-envelope-open-text"),
                    html.Span(""),
                    html.Div(
                        dbc.Badge(id='log-warns', color="danger", className='p-2'),
                        id='msg-alert-box',
                        className='right-corner-box',
                        hidden=True
                    )
                ],
                href="/logs",
                active="exact",
                className='position-relative'
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
        n_run_rows,
        market_sort_options,
        n_strat_rows,
        strat_tbl_cols,
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
                        log_div(),
                        market_div(mkt_tbl_cols, n_mkt_rows, market_sort_options),
                        runners_div(n_run_rows),
                        timings_div(n_tmr_rows),
                        strat_div(n_strat_rows, strat_tbl_cols),
                        strat_filter_div(filter_margins),
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

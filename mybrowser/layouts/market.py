import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table


def header():
    return dbc.Row([
        dbc.Col(
            html.H2('Market Browser'),
            width='auto'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-filter"),
                id="btn-session-filter",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-sync-alt"),
                id="btn-db-refresh",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-arrow-circle-up"),
                id="btn-db-upload",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-database"),
                id="btn-db-reconnect",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-trash"),
                id="btn-strategy-delete",
                n_clicks=0,
                color='danger'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(),
        dbc.Col(
            dcc.Loading(
                html.Div(id='loading-out-session'),
                type='dot'
            ),
            className='anchor-right',
        )],
        align='center'
    )


def mkt_filters(multi, filter_margins):
    # market filters
    return [
        dcc.Dropdown(
            id='input-sport-type',
            placeholder='Sport...',
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-mkt-type',
            placeholder='Market type...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-bet-type',
            placeholder='Betting type...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-format',
            placeholder='Format...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-country-code',
            placeholder='Country...',
            multi=multi,
            optionHeight=60,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-venue',
            placeholder='Venue...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Dropdown(
            id='input-date',
            placeholder='Market date...',
            multi=multi,
            className=filter_margins
        ),
        dcc.Input(
            id='input-mkt-id',
            placeholder='Market ID filter...',
            className=filter_margins
        ),
        dbc.Button(
            id='input-mkt-clear',
            children='clear',
            className=filter_margins
        )
    ]


def query_status():
    # query text status
    return dbc.Row(dbc.Col(
        html.Div(id='market-query-status')
    ))


def mkt_table(tbl_cols, n_rows):
    # DB market browser
    return dbc.Row(dbc.Col(
        dash_table.DataTable(
            id='table-market-session',
            columns=[
                {"name": v, "id": k}
                for k, v in (tbl_cols | {'market_profit': 'Profit'}).items()
            ],
            style_cell={
                'textAlign': 'left',
                'whiteSpace': 'normal',
                'height': 'auto',
                'textOverflow': 'ellipsis',
            },
            page_size=n_rows,
            sort_action="native"
        )
    ))


def strat_filters(filter_margins):
    # strategy filters
    return [
        dcc.Dropdown(
            id='input-strategy-select',
            placeholder='Strategy...',
            className=filter_margins
        ),
        dbc.Button(
            id='input-strategy-clear',
            children='clear',
            className=filter_margins
        )
    ]
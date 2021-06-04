import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table


def header():
    # runner information header and loading bar
    return dbc.Row([
        dbc.Col(
            html.H2('Runner info'),
            width='auto',
        ),
        dbc.Col(
            dbc.Button(
                html.I(className="fas fa-bars"),
                id="btn-runners-filter",
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                children=html.I(className="fas fa-download"),
                id='button-runners',
                n_clicks=0,
                color='primary'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                html.I(className='fas fa-trash'),
                id='button-mkt-bin',
                color='warning'
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(),  # pad spacing between titles/buttons and anchored right loading bar
        dbc.Col(
            dcc.Loading(
                html.Div(id='loading-out-runners'),
                type='dot',
                parent_className='anchor-right'
            )
        )],
        align='center'
        # className='d-flex align-items-center',
    )


def inputs():
    # market/runner buttons
    return html.Div(dbc.Row([
        dbc.Col(
            dbc.Button(
                ['Orders', html.I(className='fas fa-file-invoice-dollar ml-2')],
                id='button-orders',
                color='primary',
            ),
            width='auto',
            className='pr-1'
        ),
        dbc.Col(
            dbc.Button(
                ['Figure', html.I(className="fas fa-chart-line ml-2")],
                id='button-figure',
                color='primary',
            ),
            width='auto',
            className='p-1'
        ),
        dbc.Col(
            dbc.Button(
                ['All figs', html.I(className="fas fa-chart-line ml-2")],
                id='button-all-figures',
                color='secondary',
            ),
            width='auto',
            className='p-1'
        ),
        # dbc.Col(
        #     dbc.Button(
        #         ['Timings', html.I(className='fas fa-hourglass ml-2')],
        #         id='button-timings',
        #         color='primary'
        #     ),
        #     width='auto',
        #     className='p-1'
        # ),
        dbc.Col(),
        dbc.Col(
            dcc.Loading(
                html.Div(id='loading-out-figure'),
                type='dot',
                parent_className='anchor-right'
            )
        )], no_gutters=True, align='center'
    ))


def market_info():
    # information about market
    return html.Div(children=[], id='infobox-market')


def table(n_rows):
    """
    get empty mydash DataTable for runner information
    """
    return dash_table.DataTable(
        id='table-runners',
        columns=[{
            'name': v, 'id': v
        } for v in [
            'Selection ID',
            'Name',
            'Starting Odds',
            'Profit',
        ]],
        style_cell={
            'textAlign': 'left',
        },
        page_size=n_rows,
        sort_action='native',
    )

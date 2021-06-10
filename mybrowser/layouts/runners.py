import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table


def runners_config_spec(config):
    full_tbl_cols = dict(config['RUNNER_TABLE_COLS'])
    n_rows = int(config['TABLE']['runner_rows'])
    return {
        'container-id': 'container-runners',
        'header_right': [
            {
                'type': 'element-loading',
                'id': 'loading-out-runners',
            },
            {
                'type': 'element-loading',
                'id': 'loading-out-figure'
            }
        ],
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Runner Info'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-runners-filter',
                    'btn_icon': 'fas fa-bars'
                },
                {
                    'type': 'element-button',
                    'id': 'button-mkt-bin',
                    'btn_icon': 'fas fa-trash',
                    'color': 'warning',
                }
            ],
            [
                {
                    'type': 'element-button',
                    'id': 'button-orders',
                    'btn_icon': 'fas fa-file-invoice-dollar',
                    'btn_text': 'Orders',
                    'color': 'info',
                },
                {
                    'type': 'element-button',
                    'id': 'button-figure',
                    'btn_icon': 'fas fa-chart-line',
                    'btn_text': 'Figure',
                },
                {
                    'type': 'element-button',
                    'id': 'button-all-figures',
                    'btn_icon': 'fas fa-chart-line',
                    'btn_text': 'All Figures',
                },
            ],
            [
                {
                    'type': 'element-div',
                    'id': 'infobox-market'
                }
            ],
            {
                'type': 'element-table',
                'id': 'table-runners',
                'columns': full_tbl_cols,
                'n_rows': n_rows
            }
        ],
        'sidebar': {
            'sidebar_id': 'container-filters-plot',
            'sidebar_title': 'Plot Config',
            'close_id': 'btn-plot-close',
            'content': [
                {
                    'type': 'element-select',
                    'id': 'input-feature-config',
                    'placeholder': 'Feature config...'
                },
                {
                    'type': 'element-select',
                    'id': 'input-plot-config',
                    'placeholder': 'Plot config...',
                },
                {
                    'type': 'element-button',
                    'id': 'button-feature-config',
                    'btn_text': 'Reload feature configs',
                    'btn_icon': 'fas fa-sync-alt',
                    'color': 'info'
                },
                {
                    'type': 'element-input-group',
                    'children_spec': [
                        {
                            'type': 'element-input-group-addon',
                            'children_spec': 'Input offset: ',
                        },
                        {
                            'type': 'element-input',
                            'id': 'input-chart-offset',
                            'element_kwargs': {
                                'type': 'time',
                                'step': '1',  # forces HTML to use hours, minutes and seconds format
                                'value': config['PLOT_CONFIG']['default_offset']
                            }
                        }
                    ]
                }
            ]
        }
    }


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
        dbc.Col(),
        dbc.Col(
            dcc.Loading(
                html.Div(id='loading-out-figure'),
                type='dot',
                parent_className='anchor-right'
            )
        )], align='center'
    ))


def market_info():
    # information about market
    return html.Div(children=[], id='infobox-market')


def table(n_rows):
    """
    get empty mydash DataTable for runner information
    """
    return html.Div(dash_table.DataTable(
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
            'whiteSpace': 'normal',
            'height': 'auto',
            'maxWidth': 0,  # fix column widths
            'verticalAlign': 'middle'
        },
        style_header={
            'fontWeight': 'bold'
        },
        page_size=n_rows,
    ), className='table-container')


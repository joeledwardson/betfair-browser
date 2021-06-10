import dash_html_components as html
from dash_table import DataTable


def timings_config_spec(config):
    tbl_cols = dict(config['TIMINGS_TABLE_COLS'])
    n_rows = int(config['TABLE']['timings_rows'])
    return {
        'container-id': 'container-timings',
        'content': [
            [
                {
                    'type': 'header',
                    'children_spec': 'Function Timings'
                },
            ],
            {
                'type': 'table',
                'id': 'table-timings',
                'columns': tbl_cols,
                'n_rows': n_rows
            }
        ]
    }


def header():
    # orders header
    return html.H2(
        children='Function Timings',
    )


def table(n_rows):
    # function timings table
    return DataTable(
        id='table-timings',
        style_cell={
            'textAlign': 'left',
        },
        columns=[{
            'name': x,
            'id': x
        } for x in [
            'Function',
            'Count',
            'Mean',
        ]],
        page_size=n_rows,
    )



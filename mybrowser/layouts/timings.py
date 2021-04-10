import dash_html_components as html
from dash_table import DataTable
from .configs import config


def header():
    # orders header
    return html.H2(
        children='Function Timings',
    )


def table():
    # function timings table
    return html.Div(
        DataTable(
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
            page_size=int(config['TABLE']['timings_rows']),
        ),
    )


import dash_html_components as html
from dash_table import DataTable


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



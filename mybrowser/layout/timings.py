import dash_html_components as html
from dash_table import DataTable


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
            # fixed_rows={
            #     'headers': True,
            # },
            columns=[{
                'name': x,
                'id': x
            } for x in [
                'Function',
                'Count',
                'Mean',
            ]],
            page_size=8,
        ),
    )


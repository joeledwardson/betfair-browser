import dash_html_components as html
import pandas as pd
from ..tables.table import create_table


def header():
    # orders header
    return html.H2(
        children='Function Timings',
    )


def table():
    # function timings table
    return html.Div(
        children=create_table(
            table_id='table-timings',
            df=pd.DataFrame(columns=[
                'Function',
                'Count',
                'Mean',
            ]),
            height=340,
        ),
    )


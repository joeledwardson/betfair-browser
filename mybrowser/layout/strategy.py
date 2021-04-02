from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_table
import pandas as pd


def filters():
    # strategy filters
    return html.Div(
        style={
            'margin': '10px 0px',
            'width': '50%',
            'display': 'grid',
            'grid-template-columns': '1fr 1fr',
            'grid-row-gap': '2px',
            'grid-column-gap': '8px',
        },
        children=[
            dcc.Dropdown(
                id='input-strategy-select',
                placeholder='Strategy...'
            ),
            html.Button(
                id='input-strategy-clear',
                children='clear',
            ),
        ],
    )

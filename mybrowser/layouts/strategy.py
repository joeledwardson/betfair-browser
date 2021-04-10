from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from .defs import FILTER_MARGINS


def filters():
    # strategy filters
    return [
        dcc.Dropdown(
            id='input-strategy-select',
            placeholder='Strategy...',
            className=FILTER_MARGINS
        ),
        dbc.Button(
            id='input-strategy-clear',
            children='clear',
            className=FILTER_MARGINS
        )
    ]

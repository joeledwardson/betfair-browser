from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_table
import pandas as pd
from myutils import mytiming
from ..config import config
from myutils.mydash import intermediate


def inputs(feature_config_initial, plot_config_initial):
    # feature/plot configuration selections
    return html.Div(children=[html.Div(
        style={
            'display': 'grid',
            'grid-template-columns': 'auto auto',
            'grid-row-gap': '2px',
            'grid-column-gap': '8px',
        },
        children=[
            dcc.Dropdown(
                id='input-feature-config',
                placeholder='Select feature config',
                # style={
                #     'margin': '4px 2px'
                # },
                value=feature_config_initial,
            ),
            dcc.Dropdown(
                id='input-plot-config',
                placeholder='Select plot config',
                # style={
                #     'margin': '4px 2px'
                # },
                value=plot_config_initial,
            ),
        ]
    )])


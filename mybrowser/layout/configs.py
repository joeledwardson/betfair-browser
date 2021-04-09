from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from myutils import mytiming
from ..config import config
from myutils.mydash import intermediate


def inputs(feature_config_initial, plot_config_initial):
    # feature/plot configuration selections
    opts = [
        html.Div(
            dcc.Dropdown(
                id='input-feature-config',
                placeholder='Select feature config',
                value=feature_config_initial
            ),
            className='mb-2'
        ),
        html.Div(
            dcc.Dropdown(
                id='input-plot-config',
                placeholder='Select plot config',
                value=plot_config_initial
            ),
            className='mb-2'
        ),
        html.Div(
            dbc.Button(
                'reload feature configs',
                id='button-feature-config',
                n_clicks=0,
                color='info',
                block=True
            ),
            className='mb-2'
        ),
        dbc.Row([
            dbc.Col(
                html.Div('Input offset: '),
                className='mr-1',
                width='auto'
            ),
            dbc.Col(
                dbc.Input(
                    id='input-chart-offset',
                    type='time',
                    value="01:02:03",  # mytiming.format_timedelta(chart_offset),
                    # style=input_styles,
                    step="1",
                )
            )],
            align='center',
            className='mb-2'
        ),
        *[html.P(str(i)) for i in range(20)]
    ]

    return html.Div(
        html.Div(
            opts,
            className='d-flex flex-column pr-2'
        ),
        className='flex-row flex-grow-1 y-scroll',
    )


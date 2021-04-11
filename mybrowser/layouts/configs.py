import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
from ..config import config
from ._defs import filter_margins


def inputs():
    # feature/plot configuration selections
    opts = [
        dcc.Dropdown(
            id='input-feature-config',
            placeholder='Select feature config',
            className=filter_margins()
        ),
        dcc.Dropdown(
            id='input-plot-config',
            placeholder='Select plot config',
            className=filter_margins()
        ),
        dbc.Button(
            'reload feature configs',
            id='button-feature-config',
            n_clicks=0,
            color='info',
            block=True,
            className=filter_margins()
        ),
        dbc.Row([
            dbc.Col(
                html.Div('Input offset: '),
                width='auto'
            ),
            dbc.Col(
                dbc.Input(
                    id='input-chart-offset',
                    type='time',
                    value=config['PLOT_CONFIG']['default_offset'],
                    step="1"  # forces HTML to use hours, minutes and seconds format
                )
            )],
            align='center',
            className=filter_margins()
        )
    ]

    return html.Div(
        html.Div(
            opts,
            className='d-flex flex-column pr-2'
        ),
        className='flex-row flex-grow-1 y-scroll',
    )


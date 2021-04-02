from typing import Optional
from datetime import timedelta
import dash_html_components as html
from ..data import DashData
from . import market, strategy, runners, configs, orders, timings, logging
from myutils.mydash import intermediate
from myutils import mytiming


# set files table height as it is needed when re-created in callbacks
# FilesTableProperties.height = '20vh'

input_styles = {
    'margin': '3px 2px',
}


def infobox(height=70, **kwargs) -> html.Div:
    return html.Div(
        style={
            'height': height,
            'overflow-y': 'auto',
        },
        **kwargs,
    )


multi = False


# TODO make layout into different functions that are called

col_style = {
    'margin': '10px 25px',
}


def get_layout(
        input_dir: str,
        dash_data: DashData,
        chart_offset: timedelta,
        feature_config_initial: Optional[str] = None,
        plot_config_initial: Optional[str] = None,
) -> html.Div:
    # container
    return html.Div(
        style={
            'display': 'grid',
            'grid-template-columns': '50% 50%',
            'height': '100vh',
            'position': 'relative',
        },
        children=[
            intermediate.hidden_div('intermediary-market'),
            intermediate.hidden_div('intermediary-featureconfigs'),
            intermediate.hidden_div('intermediary-figure'),
            intermediate.hidden_div('intermediary-libs'),
            intermediate.hidden_div('intermediary-orders'),
            intermediate.hidden_div('intermediary-files'),
            intermediate.hidden_div('intermediary-mkt-type'),
            intermediate.hidden_div('intermediary-db-market'),

            # left column container
            html.Div(
                style=col_style,
                children=[
                    html.H1(children='Betfair Browser'),

                    market.header(),
                    market.filters(multi=False),
                    strategy.filters(),
                    market.query_status(),
                    market.table(),

                    html.Br(),

                    runners.header(),
                    runners.inputs(input_styles, chart_offset),
                    configs.inputs(feature_config_initial, plot_config_initial),
                    runners.market_info(),
                    runners.table(200),
                ]
            ),

            # right column container
            html.Div(
                style=col_style,
                children=[
                    orders.header(),
                    orders.table(340),

                    timings.header(),
                    timings.table(),
                ]
            ),

            # log box
            logging.log_box(),
        ],
    )

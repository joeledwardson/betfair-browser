import re
from datetime import datetime, timedelta
from os import path
from typing import List, Dict
import dash
from dash.dependencies import Output, Input, State

from ...tradetracker.orderinfo import get_order_updates
from ...utils.storage import EXT_ORDER_INFO, EXT_FEATURE
from ...visual.figure import generate_feature_plot

from ..data import DashData
from ..tables.runners import get_runner_id
from ..text import html_lines


def get_chart_offset(chart_offset_str):
    """
    get chart offset based on HH:MM:SS form, return datetime on success, or None on fail
    """
    if re.match(r'^\d{2}:\d{2}:\d{2}$', chart_offset_str):
        try:
            t = datetime.strptime(chart_offset_str, "%H:%M:%S")
            return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
        except ValueError:
            pass
    return None


def get_orders_df(market_dir: str, market_id: str, selection_id: int, info_strings: List[str]):
    """
    get orders dataframe based off selection ID of runner and market directory
    """

    # set orders dataframe as default if not found
    orders_df = None

    # construct orderinfo file path form market ID
    order_file_path = path.join(
        market_dir,
        market_id + EXT_ORDER_INFO
    )

    # get orders dataframe if file exists and not empty
    if path.isfile(order_file_path):
        orders_df = get_order_updates(order_file_path)
        if orders_df.shape[0]:
            orders_df = orders_df[orders_df['selection_id'] == selection_id]
        else:
            orders_df = None

    if orders_df is None:
        orders_str = f'"{order_file_path}" not found'
    else:
        orders_str = f'found {orders_df.shape[0]} order infos in "{order_file_path}"'
    info_strings.append(orders_str)
    return orders_df


def figure_callback(app: dash.Dash, dd: DashData, input_dir: str):
    """
    create a plotly figure based on selected runner when "figure" button is pressed
    """
    @app.callback(
        output=Output('infobox-figure', 'children'),
        inputs=[
            Input('button-figure', 'n_clicks')
        ],
        state=[
            State('table-runners', 'active_cell'),
            State('input-chart-offset', 'value'),
        ]
    )
    def fig_button(fig_button_clicks, runners_active_cell, chart_offset_str):

        # get datetime/None chart offset from time input
        chart_offset = get_chart_offset(chart_offset_str)

        # add runner selected cell and chart offset time to infobox
        info_strings = list()
        info_strings.append(f'Runners active cell: {runners_active_cell}')
        info_strings.append(f'Chart offset: {chart_offset}')

        # if no active market selected then abort
        if not dd.record_list or not dd.market_info:
            info_strings.append('No market information/records')
            return html_lines(info_strings)

        # get selection ID of runner from active runner cell, or abort on fail
        selection_id = get_runner_id(runners_active_cell, dd.start_odds, info_strings)
        if not selection_id:
            return html_lines(info_strings)

        # get orders dataframe (or None)
        orders_df = get_orders_df(dd.market_dir, dd.market_info.market_id, selection_id, info_strings)

        # get selection ID name from market info
        name = dd.market_info.names.get(selection_id, 'name not found')
        info_strings.append(f'producing figure for runner {selection_id}, "{name}"')

        # make chart title
        title = '{}, name: "{}", ID: "{}"'.format(
            dd.market_info,
            dd.market_info.names.get(selection_id, ""),
            selection_id,
        )

        # if chart offset specified then use as display offset, otherwise ignore
        display_seconds = chart_offset.total_seconds() if chart_offset else 0

        # construct feature info
        feature_info_path = path.join(
            dd.market_dir,
            str(selection_id) + EXT_FEATURE
        )

        # create features and figure from record list (using defaults)
        fig = generate_feature_plot(
            hist_records=dd.record_list,
            selection_id=selection_id,
            display_seconds=display_seconds,
            title=title,
            orders_df=orders_df
        )

        # display figure
        fig.show()
        return html_lines(info_strings)
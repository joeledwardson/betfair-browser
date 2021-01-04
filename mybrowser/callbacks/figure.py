import re
from datetime import datetime, timedelta
from os import path
from typing import List, Dict, Union
import dash
from dash.dependencies import Output, Input, State
from importlib import reload
from ..data import DashData
from ..tables.runners import get_runner_id
from ..text import html_lines

from mytrading.tradetracker import orderinfo
from mytrading.utils import storage as utils_storage
from mytrading.feature import storage as features_storage
from mytrading.visual import figure as figurelib
from mytrading.visual import config as configlib



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


def get_config(
        selected_name,
        config_dict: Dict[str, Dict],
        info_strings: List[str],
        config_type: str,
) -> Union[None, Dict]:
    """
    get feature/plot configurations seeing if name selected by name in dropdown is valid, otherwise getting default
    configuration

    Returns
    -------

    """

    # check if no configuration selected from dropdown
    if selected_name is None:

        # use default
        info_strings.append(f'no {config_type} configuration specified, using default')
        return None

    else:

        # config name specified in dropdown, check is id dict
        if selected_name in config_dict:

            info_strings.append(f'using {config_type} configuration: "{selected_name}"')
            return config_dict[selected_name]

        else:

            # configuration not found
            info_strings.append(f'{config_type} configuration "{selected_name}" not found in list, using default')
            return None


def get_orders_df(market_dir: str, market_id: str, info_strings: List[str]):
    """
    get orders dataframe based off market directory
    """

    # set orders dataframe as default if not found
    orders_df = None

    # construct orderinfo file path form market ID
    order_file_name = market_id + utils_storage.EXT_ORDER_INFO
    order_file_path = path.join(
        market_dir,
        order_file_name
    )

    # check order info file exists
    if path.isfile(order_file_path):

        # get order updates to dataframe
        orders_df = orderinfo.get_order_updates(order_file_path)

        # check if not empty
        if orders_df.shape[0]:

            # filter market close orders
            orders_df = orderinfo.filter_market_close(orders_df)

        else:

            # set dataframe to None if empty to indicate fail
            orders_df = None

    if orders_df is None:
        info_strings.append(f'"{order_file_name}" not found')
        return None
    else:
        count = orders_df.shape[0]
        info_strings.append(f'found {count} order infos in "{order_file_path}"')
        if count:
            return orders_df
        else:
            return None


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
            State('input-feature-config', 'value'),
            State('input-plot-config', 'value')
        ]
    )
    def fig_button(btn_clicks, runners_cell, chart_offset_str, feature_config_name, plot_config_name):

        # get datetime/None chart offset from time input
        chart_offset = get_chart_offset(chart_offset_str)

        # add runner selected cell and chart offset time to infobox
        info_strings = list()
        info_strings.append(f'Runners active cell: {runners_cell}')
        info_strings.append(f'Chart offset: {chart_offset}')

        # if no active market selected then abort
        if not dd.record_list or not dd.market_info:
            info_strings.append('No market information/records')
            return html_lines(info_strings)

        # get selection ID of runner from active runner cell, or abort on fail
        selection_id = get_runner_id(runners_cell, dd.start_odds, info_strings)
        if not selection_id:
            return html_lines(info_strings)

        # get orders dataframe (or None)
        orders_df = get_orders_df(dd.market_dir, dd.market_info.market_id, info_strings)

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

        # get first book datetime
        first_datetime = dd.record_list[0][0].publish_time

        # get market time from market info
        market_time = dd.market_info.market_time

        # get start of chart datetime
        chart_start = figurelib.get_chart_start(display_seconds, market_time, first_datetime)

        # use market start as end
        chart_end = market_time

        # check if orders dataframe exist
        if orders_df is not None:

            # filter to selection ID
            orders_df = orders_df[orders_df['selection_id'] == selection_id]

            # modify chart start/end based on orders dataframe
            chart_start = figurelib.modify_start(chart_start, orders_df, figurelib.ORDER_OFFSET_SECONDS)
            chart_end = figurelib.modify_end(chart_end, orders_df, figurelib.ORDER_OFFSET_SECONDS)

        # get plot configuration
        feature_plot_configs = get_config(plot_config_name, dd.plot_configs, info_strings, config_type='plot')

        # use default plot configuration if none selected
        feature_plot_configs = feature_plot_configs or configlib.get_plot_feature_default_configs()

        # construct feature info
        feature_info_path = path.join(
            dd.market_dir,
            str(selection_id) + utils_storage.EXT_FEATURE
        )

        # check if file exists
        if path.isfile(feature_info_path):

            # try to read features from file
            all_features_data = features_storage.features_from_file(feature_info_path)

            # check not empty
            if not len(all_features_data):

                info_strings.append(f'found feature file "{feature_info_path}" but no data')
                return html_lines(info_strings)

            else:

                info_strings.append(f'found {len(all_features_data)} features in "{feature_info_path}", plotting')

                fig = figurelib.fig_historical(
                    all_features_data=all_features_data,
                    feature_plot_configs=feature_plot_configs,
                    title=title,
                    chart_start=chart_start,
                    chart_end=chart_end,
                    orders_df=orders_df
                )

        else:

            # get feature configuration dict from selected in dropdown, leaving as None on fail
            feature_configs = get_config(feature_config_name, dd.feature_configs, info_strings, config_type='feature')

            # generate plot by simulating features
            fig = figurelib.generate_feature_plot(
                hist_records=dd.record_list,
                selection_id=selection_id,
                title=title,
                chart_start=chart_start,
                chart_end=chart_end,
                feature_plot_configs=feature_plot_configs,
                orders_df=orders_df,
                feature_configs=feature_configs
            )

        # display figure
        fig.show()
        return html_lines(info_strings)

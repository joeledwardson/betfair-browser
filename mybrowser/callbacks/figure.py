import re
from datetime import datetime, timedelta
from os import path
from typing import List, Dict, Union, Optional
import dash
from dash.dependencies import Output, Input, State
from plotly.graph_objects import Figure
from ..data import DashData
from ..tables.runners import get_runner_id
from ..logger import cb_logger
from ..intermediary import Intermediary

from mytrading.tradetracker import orderinfo
from mytrading.utils import storage as utils_storage
from mytrading.feature import storage as features_storage
from mytrading.visual import figure as figurelib
from mytrading.visual import config as configlib

counter = Intermediary()


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
        config_type: str,
) -> Optional[Dict]:
    """
    get feature/plot configurations seeing if name selected by name in dropdown is valid, otherwise getting default
    configuration

    Returns
    -------

    """

    # check if no configuration selected from dropdown
    if selected_name is None:

        # use default
        cb_logger.info(f'no {config_type} configuration specified, using default')
        return None

    else:

        # config name specified in dropdown, check is id dict
        if selected_name in config_dict:

            cb_logger.info(f'using {config_type} configuration: "{selected_name}"')
            return config_dict[selected_name]

        else:

            # configuration not found
            cb_logger.info(f'{config_type} configuration "{selected_name}" not found in list, using default')
            return None


def get_orders_df(market_dir: str, market_id: str):
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
        cb_logger.info(f'order infos file "{order_file_name}" not found')
        return None
    else:
        count = orders_df.shape[0]
        cb_logger.info(f'found {count} order infos in file "{order_file_path}"')
        if count:
            return orders_df
        else:
            return None


# def create_figure(selection_id, dd: DashData, info_strings, orders_df, all_features_data, chart_start, chart_end) -> \
#         go.Figure:
#
#     # get selection ID name from market info
#     name = dd.market_info.names.get(selection_id, 'name not found')
#     info_strings.append(f'producing figure for runner {selection_id}, "{name}"')
#
#     # make chart title
#     title = '{}, name: "{}", ID: "{}"'.format(
#         dd.market_info,
#         dd.market_info.names.get(selection_id, ""),
#         selection_id,
#     )
#
#     # check if orders dataframe exist
#     if orders_df is not None:
#
#         # filter to selection ID
#         orders_df = orders_df[orders_df['selection_id'] == selection_id]
#
#         # modify chart start/end based on orders dataframe
#         chart_start = figurelib.modify_start(chart_start, orders_df, figurelib.ORDER_OFFSET_SECONDS)
#         chart_end = figurelib.modify_end(chart_end, orders_df, figurelib.ORDER_OFFSET_SECONDS)
#
#     # construct feature info
#     feature_info_path = path.join(
#         dd.market_dir,
#         str(selection_id) + utils_storage.EXT_FEATURE
#     )
#
#     # check if file exists
#     if path.isfile(feature_info_path):
#
#         # try to read features from file
#         all_features_data = features_storage.features_from_file(feature_info_path)
#
#         # check not empty
#         if not len(all_features_data):
#
#             info_strings.append(f'found feature file "{feature_info_path}" but no data')
#             return html_lines(info_strings)
#
#         else:
#
#             info_strings.append(f'found {len(all_features_data)} features in "{feature_info_path}", plotting')
#
#             fig = figurelib.fig_historical(
#                 all_features_data=all_features_data,
#                 feature_plot_configs=feature_plot_configs,
#                 title=title,
#                 chart_start=chart_start,
#                 chart_end=chart_end,
#                 orders_df=orders_df
#             )


def figure_callback(app: dash.Dash, dd: DashData, input_dir: str):
    """
    create a plotly figure based on selected runner when "figure" button is pressed
    """
    @app.callback(
        output=Output('intermediary-figure', 'children'),
        inputs=[
            Input('button-figure', 'n_clicks')
        ],
        state=[
            State('table-runners', 'active_cell'),
            State('input-chart-offset', 'value'),
            State('input-feature-config', 'value'),
            State('input-plot-config', 'value'),
        ]
    )
    def fig_button(btn_clicks, cell, offset_str, ftr_key, plt_key):

        # get datetime/None chart offset from time input
        offset = get_chart_offset(offset_str)

        # add runner selected cell and chart offset time to infobox
        cb_logger.info('attempting to plot')
        cb_logger.info(f'runners active cell: {cell}')
        cb_logger.info(f'chart offset: {offset}')

        # if no active market selected then abort
        if not dd.record_list or not dd.market_info:
            cb_logger.info('fail: no market information/records')
            return counter.next()

        # get selection ID of runner from active runner cell, or abort on fail
        selection_id = get_runner_id(cell, dd.start_odds)
        if not selection_id:
            return counter.next()

        # get orders dataframe (or None)
        orders = get_orders_df(dd.market_dir, dd.market_info.market_id)

        # get selection ID name from market info
        name = dd.market_info.names.get(selection_id, 'name not found')
        cb_logger.info(f'producing figure for runner {selection_id}, "{name}"')

        # make chart title
        title = '{}, name: "{}", ID: "{}"'.format(
            dd.market_info,
            dd.market_info.names.get(selection_id, ""),
            selection_id,
        )

        # if chart offset specified then use as display offset, otherwise ignore
        secs = offset.total_seconds() if offset else 0

        # get first book datetime
        dt0 = dd.record_list[0][0].publish_time

        # get market time from market info
        dt_mkt = dd.market_info.market_time

        # get start of chart datetime
        start = figurelib.get_chart_start(display_seconds=secs, market_time=dt_mkt, first=dt0)

        # use market start as end
        end = dt_mkt

        # check if orders dataframe exist
        if orders is not None:

            # filter to selection ID
            orders = orders[orders['selection_id'] == selection_id]

            # modify chart start/end based on orders dataframe
            start = figurelib.modify_start(start, orders, figurelib.ORDER_OFFSET_SECONDS)
            end = figurelib.modify_end(end, orders, figurelib.ORDER_OFFSET_SECONDS)

        # get plot configuration
        plt_conf = get_config(plt_key, dd.plot_configs, config_type='plot')

        # use default plot configuration if none selected
        plt_conf = plt_conf or configlib.get_plot_feature_default_configs()

        # construct feature info
        ftr_path = path.join(
            dd.market_dir,
            str(selection_id) + utils_storage.EXT_FEATURE
        )

        # check if file exists
        if path.isfile(ftr_path):

            # try to read features from file
            ftr_data = features_storage.features_from_file(ftr_path)

            # check not empty
            if not len(ftr_data):

                cb_logger.warning(f'found feature file "{ftr_path}" but no data')
                return counter.next()

            else:

                cb_logger.info(f'found {len(ftr_data)} features in "{ftr_path}", plotting')

                fig = figurelib.fig_historical(
                    all_features_data=ftr_data,
                    feature_plot_configs=plt_conf,
                    title=title,
                    chart_start=start,
                    chart_end=end,
                    orders_df=orders
                )

        else:

            # get feature configuration dict from selected in dropdown, leaving as None on fail
            ftr_conf = get_config(ftr_key, dd.feature_configs, config_type='feature')

            # generate plot by simulating features
            fig = figurelib.generate_feature_plot(
                hist_records=dd.record_list,
                selection_id=selection_id,
                title=title,
                chart_start=start,
                chart_end=end,
                feature_plot_configs=plt_conf,
                orders_df=orders,
                feature_configs=ftr_conf
            )

        # display figure
        fig.show()
        return counter.next()


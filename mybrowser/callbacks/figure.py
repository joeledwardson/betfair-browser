import re
from datetime import datetime, timedelta
from os import path
from typing import List, Dict, Union, Optional
import dash
from dash.dependencies import Output, Input, State
import pandas as pd
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

# override visual logger with custom logger
figurelib.active_logger = cb_logger
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


def get_orders_df(market_dir: str, market_id: str) -> Optional[pd.DataFrame]:
    """
    get orders dataframe based off market directory
    """

    # set orders dataframe as default if not found
    df = None

    # construct orderinfo file path form market ID
    file_name = market_id + utils_storage.EXT_ORDER_INFO
    file_path = path.join(
        market_dir,
        file_name
    )

    # check order info file exists
    if path.isfile(file_path):

        # get order updates to dataframe
        df = orderinfo.get_order_updates(file_path)

        # check if not empty
        if df.shape[0]:

            # filter market close orders
            df = orderinfo.filter_market_close(df)

        else:

            # set dataframe to None if empty to indicate fail
            df = None

    if df is None:
        cb_logger.info(f'order infos file "{file_name}" not found')
        return None
    else:
        count = df.shape[0]
        cb_logger.info(f'found {count} order infos in file "{file_path}"')
        if count:
            return df
        else:
            return None


def get_features(
        sel_id: int,
        ftr_key: Optional[str],
        dd: DashData,
        start: datetime,
        end: datetime
) -> Optional[Dict]:

    # construct feature info
    ftr_path = path.join(
        dd.market_info.market_id,
        str(sel_id) + utils_storage.EXT_FEATURE
    )

    # store feature data
    ftr_data = None

    # check if file exists
    if path.isfile(ftr_path):

        # try to read features from file
        ftr_data = features_storage.features_from_file(ftr_path)
        cb_logger.info(f'found {len(ftr_data)} features in file "{ftr_path}"')
        if not ftr_data:
            cb_logger.info('generating features from selected configuration instead')

    # generate features if file doesn't exist or empty/fail
    if not ftr_data:

        dft = dd.feature_config_default
        if not ftr_key:
            cfg_key = dft
            cb_logger.info(f'no feature config selected, using default "{dft}"')
        else:
            if ftr_key not in dd.feature_configs:
                cb_logger.warning(f'selected feature config "{ftr_key}" not found in list, using default "{dft}"')
                cfg_key = dft
            else:
                cb_logger.info(f'using selected feature config "{ftr_key}"')
                cfg_key = ftr_key

        cfg = dd.feature_configs.get(cfg_key)
        if not cfg:
            cb_logger.warning(f'feature config "{cfg_key}" empty')
            return None

        # generate plot by simulating features
        ftr_data = figurelib.generate_feature_data(
            hist_records=dd.record_list,
            selection_id=sel_id,
            chart_start=start,
            chart_end=end,
            feature_configs=cfg
        )

    return ftr_data


def plot_runner(
        sel_id: int,
        dd: DashData,
        orders: Optional[pd.DataFrame],
        start: datetime,
        end: datetime,
        ftr_key: Optional[str],
        plt_cfg: Dict
):

    # get name from market info
    name = dd.market_info.names.get(sel_id, 'name not found')
    cb_logger.info(f'producing figure for runner {sel_id}, "{name}"')

    # make chart title
    title = '{}, name: "{}", ID: "{}"'.format(dd.market_info, name, sel_id)

    # check if orders dataframe exist
    if orders is not None:

        # filter to selection ID
        orders = orders[orders['selection_id'] == sel_id]

        # modify chart start/end based on orders dataframe
        start = figurelib.modify_start(start, orders, figurelib.ORDER_OFFSET_SECONDS)
        end = figurelib.modify_end(end, orders, figurelib.ORDER_OFFSET_SECONDS)

    # get feature data from either features file or try to generate, check not empty
    ftr_data = get_features(sel_id, ftr_key, dd, start, end)
    if not ftr_data:
        cb_logger.warning('feature data empty')
        return counter.next()

    # generate figure
    fig = figurelib.fig_historical(
        all_features_data=ftr_data,
        feature_plot_configs=plt_cfg,
        title=title,
        chart_start=start,
        chart_end=end,
        orders_df=orders
    )

    # display figure
    fig.show()


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
            cb_logger.warning('fail: no market information/records')
            return counter.next()

        # get orders dataframe (or None)
        orders = get_orders_df(dd.market_dir, dd.market_info.market_id)

        # if chart offset specified then use as display offset, otherwise ignore
        secs = offset.total_seconds() if offset else 0

        # get first book datetime
        dt0 = dd.record_list[0][0].publish_time

        # get market time from market info
        dt_mkt = dd.market_info.market_time

        # use market start as end
        end = dt_mkt

        # get start of chart datetime
        start = figurelib.get_chart_start(display_seconds=secs, market_time=dt_mkt, first=dt0)

        # get plot configuration
        plt_cfg = {}
        if plt_key:
            if plt_key in dd.plot_configs:
                cb_logger.info(f'using selected plot configuration "{plt_key}"')
                plt_cfg = dd.plot_configs[plt_key]
            else:
                cb_logger.warning(f'selected plot configuration "{plt_key}" not in plot configurations')
        else:
            cb_logger.info('no plot configuration selected')

        # get selection ID of runner from active runner cell, or abort on fail
        sel_id = get_runner_id(cell, dd.start_odds)
        if not sel_id:
            return counter.next()

        plot_runner(
            sel_id=sel_id,
            dd=dd,
            orders=orders,
            start=start,
            end=end,
            ftr_key=ftr_key,
            plt_cfg=plt_cfg
        )
        return counter.next()


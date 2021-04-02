import re
from functools import partial
from datetime import datetime, timedelta
from os import path
from typing import List, Dict, Union, Optional
import dash
from dash.dependencies import Output, Input, State
import pandas as pd
from plotly.graph_objects import Figure
import logging
from ..data import DashData
from ..tables.runners import get_runner_id
from ..app import app, dash_data as dd
from .globals import IORegister
from mytrading.tradetracker import orderinfo
from mytrading.utils import storage as utils_storage
from mytrading.feature import storage as features_storage
from mytrading.visual import figure as figurelib
from mytrading.visual import config as configlib
from myutils.mydash import context as my_context
from myutils import mytiming
from myutils.mydash import intermediate


# override visual logger with custom logger
active_logger = logging.getLogger(__name__)
figurelib.active_logger = active_logger
counter = intermediate.Intermediary()

mid = Output('intermediary-figure', 'children')
inputs = [
    Input('button-figure', 'n_clicks'),
    Input('button-all-figures', 'n_clicks'),
]
IORegister.register_inputs(inputs)
IORegister.register_mid(mid)


def get_chart_offset(chart_offset_str) -> Optional[timedelta]:
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
        active_logger.info(f'order infos file "{file_name}" not found')
        return None
    else:
        count = df.shape[0]
        active_logger.info(f'found {count} order infos in file "{file_path}"')
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
    """
    get dictionary of feature name to RunnerFeatureBase instance from either features file (search for it in directory)
    or if no feature file, try to generate based on feature configuration `ftr_key`
    """

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
        active_logger.info(f'found {len(ftr_data)} features in file "{ftr_path}"')
        if not ftr_data:
            active_logger.info('generating features from selected configuration instead')

    # generate features if file doesn't exist or empty/fail
    if not ftr_data:

        dft = dd.feature_config_default
        if not ftr_key:
            cfg_key = dft
            active_logger.info(f'no feature config selected, using default "{dft}"')
        else:
            if ftr_key not in dd.feature_configs:
                active_logger.warning(f'selected feature config "{ftr_key}" not found in list, using default "{dft}"')
                cfg_key = dft
            else:
                active_logger.info(f'using selected feature config "{ftr_key}"')
                cfg_key = ftr_key

        cfg = dd.feature_configs.get(cfg_key)
        if not cfg:
            active_logger.warning(f'feature config "{cfg_key}" empty')
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
) -> None:
    """
    plot and show a plotly figure for a runner and a designated feature/plot configuration
    """

    # get name from market info
    name = dd.runner_names.get(sel_id, 'name not found')
    active_logger.info(f'producing figure for runner {sel_id}, "{name}"')

    # make chart title
    title = '{} {} {} "{}", name: "{}", ID: "{}"'.format(
        dd.db_mkt_info['event_name'],
        dd.db_mkt_info['market_time'],
        dd.db_mkt_info['market_type'],
        dd.db_mkt_info['market_id'],
        name,
        sel_id
    )
    # f'{self.event_name} {market_time} {self.market_type} "{self.market_id}"'

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
        active_logger.warning('feature data empty')
        return

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


@app.callback(
    output=[
        Output('table-timings', 'data'),
        mid,
    ],
    inputs=inputs,
    state=[
        State('table-runners', 'active_cell'),
        State('input-chart-offset', 'value'),
        State('input-feature-config', 'value'),
        State('input-plot-config', 'value'),
        State('checklist-timings', 'value')
    ]
)
def fig_button(clicks0, clicks1, cell, offset_str, ftr_key, plt_key, tmr_vals):
    """
    create a plotly figure based on selected runner when "figure" button is pressed
    """

    ret = [list(), counter.next()]

    # get datetime/None chart offset from time input
    offset = get_chart_offset(offset_str)

    # add runner selected cell and chart offset time to infobox
    active_logger.info('attempting to plot')
    active_logger.info(f'runners active cell: {cell}')
    active_logger.info(f'chart offset: {offset}')

    # if no active market selected then abort
    if not dd.record_list or not dd.db_mkt_info:
        active_logger.warning('no market information/records')
        return ret

    # get orders dataframe (or None)
    if dd.strategy_id:
        p = path.join(dd.file_tracker.root, 'strategycache', dd.strategy_id, dd.db_mkt_info['market_id'])
        p = path.abspath(p)
        if not path.exists(p):
            active_logger.warning(f'could not find cached strategy market file:\n-> "{p}"')
            return ret

        orders = orderinfo.get_order_updates(p)
        if not orders.shape[0]:
            active_logger.warning(f'could not find any rows in cached strategy market file:\n-> "{p}"')
            return ret

        active_logger.info(f'loaded {orders.shape[0]} rows from cached strategy market file\n-> "{p}"')
    else:
        orders = pd.DataFrame()

    # orders = get_orders_df(dd.market_dir, dd.db_mkt_info['market_id'])

    # if chart offset specified then use as display offset, otherwise ignore
    secs = offset.total_seconds() if offset else 0

    # get first book datetime
    dt0 = dd.record_list[0][0].publish_time

    # get market time from market info
    dt_mkt = dd.db_mkt_info['market_time']

    # use market start as end
    end = dt_mkt

    # get start of chart datetime
    start = figurelib.get_chart_start(display_seconds=secs, market_time=dt_mkt, first=dt0)

    # get plot configuration
    plt_cfg = {}
    if plt_key:
        if plt_key in dd.plot_configs:
            active_logger.info(f'using selected plot configuration "{plt_key}"')
            plt_cfg = dd.plot_configs[plt_key]
        else:
            active_logger.warning(f'selected plot configuration "{plt_key}" not in plot configurations')
    else:
        active_logger.info('no plot configuration selected')

    # determine if 'all feature plots' clicked as opposed to single plot
    do_all = my_context.triggered_id() == 'button-all-figures'

    sel_ids = []
    if do_all:

        # do all selection IDs
        sel_ids = list(dd.start_odds.keys())

    else:

        # get selection ID of runner from active runner cell, or abort on fail
        if not cell:
            active_logger.warning('no cell selected')
            return ret

        if 'row_id' not in cell:
            active_logger.warning(f'row ID not found in active cell info')
            return ret

        sel_id = cell['row_id']
        if not sel_id:
            active_logger.warning(f'selection ID is blank')
            return ret
        sel_ids = [sel_id]

    try:
        for sel_id in sel_ids:
            plot_runner(
                sel_id=sel_id,
                dd=dd,
                orders=orders,
                start=start,
                end=end,
                ftr_key=ftr_key,
                plt_cfg=plt_cfg
            )
    except (ValueError, TypeError) as e:
        active_logger.error('plot error', e, exc_info=True)

    if sel_ids and tmr_vals:
        tms = mytiming.get_timings_summary()
        mytiming.clear_timing_register()
        if not tms:
            active_logger.warning('no timings on which to produce table')
        tms = sorted(tms, key=lambda v: v['Mean'], reverse=True)
        # TODO add to configuration file
        td_fmt = '{d}d {h:02}:{m:02}:{s:02}.{u:06}'
        f = partial(mytiming.format_timedelta, fmt=td_fmt)
        tms = [{
            k: f(v) if k == 'Mean' else v
            for k, v in t.items() if k in ['Function', 'Count', 'Mean']
        } for t in tms]
        ret[1] = tms

    return ret



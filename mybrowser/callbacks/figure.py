import re
from functools import partial
from datetime import datetime, timedelta
from os import path
from typing import List, Dict, Union, Optional
from dash.dependencies import Output, Input, State
import pandas as pd
import logging

from ..data import DashData
from ..app import app, dash_data as dd
from .. import bfcache
from ..config import config

from mytrading.tradetracker import orderinfo
from mytrading.utils import storage as utils_storage
from mytrading.visual import figure as figurelib
from myutils.mydash import context as my_context
from myutils import mytiming
from myutils.mydash import intermediate


# override visual logger with custom logger
active_logger = logging.getLogger(__name__)
figurelib.active_logger = active_logger
counter = intermediate.Intermediary()


def get_timings() -> List[Dict]:
    tms = mytiming.get_timings_summary()
    if not tms:
        active_logger.warning('no timings on which to produce table')
        return list()
    tms = sorted(tms, key=lambda v: v['Mean'], reverse=True)
    td_fmt = config['TIMING_CONFIG']['str_format']
    f = partial(mytiming.format_timedelta, fmt=td_fmt)
    tms = [{
        k: f(v) if k == 'Mean' else v
        for k, v in t.items() if k in ['Function', 'Count', 'Mean']
    } for t in tms]
    return tms


def get_ids(cell, id_list) -> Optional[List[int]]:
    """
    get a list of selection IDs for runners on which to plot charts
    if `do_all` is True, then simply return complete `id_list` - if not, take row ID from cell as single selection ID
    for list and validate
    """

    # determine if 'all feature plots' clicked as opposed to single plot
    do_all = my_context.triggered_id() == 'button-all-figures'

    if do_all:

        # do all selection IDs
        return id_list

    else:

        # get selection ID of runner from active runner cell, or abort on fail
        if not cell:
            active_logger.warning('no cell selected')
            return None

        if 'row_id' not in cell:
            active_logger.warning(f'row ID not found in active cell info')
            return None

        sel_id = cell['row_id']
        if not sel_id:
            active_logger.warning(f'selection ID is blank')
            return None
        return [sel_id]


def get_plot_config(plt_key: str, plot_configs: Dict[str, Dict]) -> Dict:
    """
    get plot configuration or empty dictionary
    """
    plt_cfg = {}
    if plt_key:
        if plt_key in plot_configs:
            active_logger.info(f'using selected plot configuration "{plt_key}"')
            plt_cfg = plot_configs[plt_key]
        else:
            active_logger.warning(f'selected plot configuration "{plt_key}" not in plot configurations')
    else:
        active_logger.info('no plot configuration selected')
    return plt_cfg


def get_orders(strategy_id, mkt_info) -> Union[pd.DataFrame, None]:
    """
    get dataframe of order updates (datetime set as index), empty dataframe if strategy not specified,
    None if strategy specified by fail
    """

    if strategy_id:
        p = bfcache.p_strat(strategy_id, mkt_info['market_id'])
        if not path.exists(p):
            active_logger.warning(f'could not find cached strategy market file:\n-> "{p}"')
            return None

        orders = orderinfo.get_order_updates(p)
        if not orders.shape[0]:
            active_logger.warning(f'could not find any rows in cached strategy market file:\n-> "{p}"')
            return None

        active_logger.info(f'loaded {orders.shape[0]} rows from cached strategy market file\n-> "{p}"')
        return orders
    else:
        return pd.DataFrame()


def fig_title(mkt_info: Dict, name: str, selection_id: int) -> str:
    """
    generate figure title from database market meta-information, runner name and runner selection ID
    """
    return '{} {} {} "{}", name: "{}", ID: "{}"'.format(
        mkt_info['event_name'],
        mkt_info['market_time'],
        mkt_info['market_type'],
        mkt_info['market_id'],
        name,
        selection_id
    )


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

    # # construct feature info
    # ftr_path = path.join(
    #     dd.market_info.market_id,
    #     str(sel_id) + utils_storage.EXT_FEATURE
    # )

    # store feature data
    ftr_data = None

    # # check if file exists
    # if path.isfile(ftr_path):
    #
    #     # try to read features from file
    #     ftr_data = features_storage.features_from_file(ftr_path)
    #     active_logger.info(f'found {len(ftr_data)} features in file "{ftr_path}"')
    #     if not ftr_data:
    #         active_logger.info('generating features from selected configuration instead')

    # generate features if file doesn't exist or empty/fail
    if not ftr_data:

        dft = config['PLOT_CONFIG']['default_features']
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
            active_logger.error(f'feature config "{cfg_key}" empty')
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


@app.callback(
    output=[
        Output('table-timings', 'data'),
        Output('loading-out-figure', 'children'),
        Output('intermediary-figure', 'children'),
    ],
    inputs=[
        Input('button-figure', 'n_clicks'),
        Input('button-all-figures', 'n_clicks'),
    ],
    state=[
        State('table-runners', 'active_cell'),
        State('input-chart-offset', 'value'),
        State('input-feature-config', 'value'),
        State('input-plot-config', 'value')
    ]
)
def fig_button(clicks0, clicks1, cell, offset_str, ftr_key, plt_key):
    """
    create a plotly figure based on selected runner when "figure" button is pressed
    """

    ret = [
        list(),
        '',
        counter.next()
    ]

    # get datetime/None chart offset from time input
    offset_dt = get_chart_offset(offset_str)
    secs = offset_dt.total_seconds() if offset_dt else 0

    # add runner selected cell and chart offset time to infobox
    active_logger.info('attempting to plot')
    active_logger.info(f'runners active cell: {cell}')
    active_logger.info(f'chart offset: {offset_dt}')

    # if no active market selected then abort
    if not dd.record_list or not dd.db_mkt_info:
        active_logger.warning('no market information/records')
        return ret

    # get orders dataframe (or None)
    orders = get_orders(dd.strategy_id, dd.db_mkt_info)
    if orders is None:
        return ret

    # get start/end of chart datetimes
    dt0 = dd.record_list[0][0].publish_time
    mkt_dt = dd.db_mkt_info['market_time']
    start = figurelib.get_chart_start(display_seconds=secs, market_time=mkt_dt, first=dt0)

    # get plot configuration
    plt_cfg = get_plot_config(plt_key, dd.plot_configs)

    # get selected IDs
    sel_ids = get_ids(cell, list(dd.start_odds.keys()))
    if not sel_ids:
        return ret

    try:
        for sel_id in sel_ids:
            # get name and title
            name = dd.runner_names.get(sel_id, 'name not found')
            title = fig_title(dd.db_mkt_info, name, sel_id)
            active_logger.info(f'producing figure for runner {sel_id}, "{name}"')

            # chart specific vars
            chart_orders = orders
            chart_start = start
            chart_end = mkt_dt

            # check if orders dataframe exist
            if orders.shape[0]:
                # filter to selection ID, modify chart start/end based on orders dataframe
                chart_orders = orders[orders['selection_id'] == sel_id]
                chart_start = figurelib.modify_start(start, orders, figurelib.ORDER_OFFSET_SECONDS)
                chart_end = figurelib.modify_end(mkt_dt, orders, figurelib.ORDER_OFFSET_SECONDS)

            # get feature data from either features file or try to generate, check not emp
            ftr_data = get_features(sel_id, ftr_key, dd, chart_start, chart_end)
            if not ftr_data:
                active_logger.error('feature data empty')
                continue

            # generate figure
            fig = figurelib.fig_historical(
                all_features_data=ftr_data,
                feature_plot_configs=plt_cfg,
                title=title,
                chart_start=chart_start,
                chart_end=chart_end,
                orders_df=chart_orders
            )

            # display figure
            fig.show()

    except (ValueError, TypeError) as e:
        active_logger.error('plot error', e, exc_info=True)

    ret[0] = get_timings()
    mytiming.clear_timing_register()

    return ret


@app.callback(
    Output('modal-timings', 'is_open'),
    [Input('button-timings', 'n_clicks'), Input('modal-close-timings', 'n_clicks')]
)
def modal_timings(n1, n2):
    return my_context.triggered_id() == 'button-timings'


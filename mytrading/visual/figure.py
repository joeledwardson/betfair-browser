from datetime import timedelta, datetime
from typing import List, Dict

import pandas as pd
from betfairlightweight.resources import MarketBook
from plotly import graph_objects as go
from plotly.subplots import make_subplots

from ..process.ticks.ticks import LTICKS_DECODED, closest_tick
from ..tradetracker.messages import MessageTypes
from ..feature.window import Windows
from ..feature.utils import generate_features, get_feature_data, get_max_buffer_s
from ..feature.historic import hist_runner_features
from ..feature.config import get_features_default_configs
from .config import get_plot_default_config
from .feature import add_feature_trace
from .orderinfo import plot_orders
from myutils import generic
import logging

active_logger = logging.getLogger(__name__)

# number of seconds to buffer when trimming record list
PROCESS_BUFFER_S = 10

# offset either side of order info
ORDER_OFFSET_SECONDS = 2


def modify_start(chart_start: datetime, orders_df: pd.DataFrame, buffer_seconds: float) -> datetime:
    """
    set start time to first order info update received minus buffer, if less than existing chart start

    Parameters
    ----------
    chart_start :

    Returns
    -------

    """
    if orders_df.shape[0]:
        orders_start = orders_df.index[0]
        orders_start = orders_start - timedelta(seconds=buffer_seconds)
        if orders_start < chart_start:
            return orders_start
    return chart_start


def modify_end(chart_end: datetime, orders_df: pd.DataFrame, buffer_seconds: float) -> datetime:
    """
    set end time to last order info update minus received buffer, if more than existing chart end
    removes market close from data frame when looking at last order timestamp

    Parameters
    ----------
    chart_end :
    orders_df :
    buffer_seconds :

    Returns
    -------

    """
    if orders_df.shape[0]:
        trimmed_orders = orders_df[orders_df['msg_type'] != MessageTypes.MSG_MARKET_CLOSE.value]
        if trimmed_orders.shape[0]:
            orders_end = trimmed_orders.index[-1]
            orders_end = orders_end + timedelta(seconds=buffer_seconds)
            if orders_end > chart_end:
                return orders_end
    return chart_end


def get_chart_start(display_seconds: float, market_time: datetime, first: datetime) -> datetime:
    """
    get datetime of start of chart, based on `display_seconds` number which if non-zero indicates number of seconds
    before start time to use, otherwise just take `first` book timestamp

    Parameters
    ----------
    display_seconds :
    market_time :
    first :

    Returns
    -------

    """

    # check if display seconds is nonzero use offset from start time
    if display_seconds:

        # use offset from start time
        chart_start = market_time - timedelta(seconds=display_seconds)
        active_logger.info(f'using chart start {chart_start}, {display_seconds}s before market time')
        return chart_start

    else:

        # display seconds 0, just use first record
        chart_start = first
        active_logger.info(f'using first record for chart start {chart_start}')
        return chart_start


def fig_to_file(fig: go.Figure, file_path, mode='a'):
    """
    write a plotly figure to a file, default mode appending to file
    """
    with generic.create_dirs(open)(file_path, mode) as f:
        f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
    active_logger.info(f'writing figure to file "{file_path}"')


def fig_historical(
        all_features_data: Dict[str, List[Dict[str, List]]],
        feature_plot_configs: Dict[str, Dict],
        title: str,
        chart_start: datetime,
        chart_end: datetime,
        orders_df: pd.DataFrame=None,
        orders_plot_config=None
):
    """
    create figure using default features for historical record list and a selected runner ID
    - records: list of historical records
    - features: dict of {feature name: feature instance} to apply
    - feature_plot_configs: dict of {feature name: feature plot config} to apply when plotting each feature
    - selection_id: id of runner
    - title: title to apply to chart
    - display_s: number of seconds before start time to display chart for, 0 indicates ignore
    - orders_df: dataframe of order update to add as annotated scatter points
    """

    # check features dict is not empty
    if not len(all_features_data):
        active_logger.warning(f'error printing figure "{title}", feature data empty')
        return go.Figure()

    # get deafult configuration for plot chart
    default_plot_config = get_plot_default_config()

    # get list of yaxes names from feature plot configurations and default plot configuration
    y_axes_names = get_yaxes_names(feature_plot_configs, default_plot_config['y_axis'])

    # create figure based off axis names with correct number of subplots
    fig = create_figure(y_axes_names)

    # loop feature data
    for feature_name in all_features_data.keys():

        # get feature plot configuration
        conf = feature_plot_configs.get(feature_name, {})

        # add feature trace with data
        add_feature_trace(
            fig=fig,
            feature_name=feature_name,
            all_features_data=all_features_data,
            default_config=default_plot_config,
            feature_config=conf,
            y_axes_names=y_axes_names,
            chart_start=chart_start,
            chart_end=chart_end,
        )

    # if order info dataframe passed and not emptythen plot
    if orders_df is not None and orders_df.shape[0]:
        orders_df = orders_df[
            (orders_df.index >= chart_start) &
            (orders_df.index <= chart_end)
        ]
        plot_orders(fig, orders_df.copy(), orders_plot_config)

    # set figure layout and return
    set_figure_layout(fig, title, chart_start, chart_end)
    return fig


def generate_feature_plot(
        hist_records: List[List[MarketBook]],
        selection_id: int,
        title: str,
        chart_start: datetime,
        chart_end: datetime,
        feature_plot_configs: Dict,
        feature_configs: Dict = None,
        orders_df: pd.DataFrame = None,
        orders_plot_config: Dict = None,
) -> go.Figure:
    """
    create historical feature plot for a single runners based on record list, default configs and optional orders
    frame
    """

    # check record set empty
    if not hist_records:
        active_logger.warning(f'error creating figure "{title}", records set empty')
        return go.Figure()
    active_logger.info(f'creating figure from {len(hist_records)} records')

    # use default feature configuration if not passed
    if feature_configs is None:
        feature_configs = get_features_default_configs()

    # create runner feature instances (do not use feature holder as that is for a list of runners, not a single runner)
    features = generate_features(
        feature_configs=feature_configs
    )

    # get computations start buffer seconds
    buffer_s = get_max_buffer_s(features)
    chart_buffer_s = buffer_s + PROCESS_BUFFER_S
    active_logger.info(f'using {buffer_s}s + {PROCESS_BUFFER_S}s before start for computations')

    # trim records to within computation windows
    modified_start = chart_start - timedelta(seconds=chart_buffer_s)
    hist_records = [r for r in hist_records if modified_start <= r[0].publish_time <= chart_end]
    active_logger.info(f'chart start: {chart_start}, computation start time: {modified_start}, end: {chart_end}')

    # check trimmed record set not empty
    if not len(hist_records):
        active_logger.warning('trimmed records empty')
        return go.Figure()
    active_logger.info(f'trimmed record set has {len(hist_records)} records')

    # initialise features with first of trimmed books and windows
    windows = Windows()
    for feature in features.values():
        feature.race_initializer(selection_id, hist_records[0][0], windows)

    # run feature processors on historic data
    hist_runner_features(selection_id, hist_records, windows, features)

    # get feature data from feature set
    all_features_data = get_feature_data(features, pre_serialize=False)

    # create runner feature figure and append to html output path
    fig = fig_historical(
        all_features_data = all_features_data,
        feature_plot_configs=feature_plot_configs,
        title=title,
        chart_start=chart_start,
        chart_end=chart_end,
        orders_df=orders_df,
        orders_plot_config=orders_plot_config,
    )

    return fig


def get_yaxes_names(feature_plot_configs: dict, default_yaxis: str) -> List[str]:
    """get list of yaxis names from default configuration and list of feature configurations"""

    return list(set(
        [default_yaxis] + [c.get('y_axis', default_yaxis)
                           for c in feature_plot_configs.values()]
    ))


def create_figure(y_axes_names: List[str], vertical_spacing=0.05) -> go.Figure:
    """create chart with subplots based on 'y_axis' properties of feature plot configurations"""

    n_cols = 1
    n_rows = len(y_axes_names)

    return make_subplots(
        cols=n_cols,
        rows=n_rows,
        shared_xaxes=True,
        specs=[[{'secondary_y': True} for y in range(n_cols)] for x in range(n_rows)],
        vertical_spacing=vertical_spacing)


def set_figure_layout(fig: go.Figure, title: str, chart_start: datetime, chart_end: datetime):
    """
    set plotly figure layout with a title, limit x axis from start time minus display seconds
    """

    # verify trace
    def trace_verify(trace):
        return (
            'y' in trace and
            'yaxis' in trace and
            trace['yaxis'] == 'y' and
            len(trace['y']) and
            generic.constructor_verify(trace['y'][0], float)
        )

    # get primary yaxis maximum and minimum values by getting max/min of each trace
    y_min = min([
        min(trace['y'])
        for trace in fig.data
        if trace_verify(trace)
    ])
    y_max = max([
        max(trace['y'])
        for trace in fig.data
        if trace_verify(trace)
    ])

    # get index of minimum yaxis value, subtract 1 for display buffer
    i_min = closest_tick(y_min, return_index=True)
    i_min = max(0, i_min - 1)

    # get index of maximum yaxis value, add 1 for display buffer
    i_max = closest_tick(y_max, return_index=True)
    i_max = min(len(LTICKS_DECODED) - 1, i_max + 1)

    # set title
    fig.update_layout(title=title)

    # remove range slider and set chart xaxis display limits
    fig.update_xaxes({
        'rangeslider': {
            'visible': False
        },
        'range':  [
            chart_start,
            chart_end
        ],
    })

    # set primary yaxis gridlines to betfair ticks within range
    fig.update_yaxes({
        'tickmode': 'array',
        'tickvals': LTICKS_DECODED[i_min:i_max+1],
    })

    # set secondary yaxis, manually set ticks to auto and number to display or for some reason they appear bunched up?
    fig.update_yaxes({
        'showgrid': False,
        'tickmode': 'auto',
        'nticks': 10,
    }, secondary_y=True)

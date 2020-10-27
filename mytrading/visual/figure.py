from datetime import timedelta, datetime
from typing import List, Dict

import pandas as pd
from betfairlightweight.resources import MarketBook
from plotly import graph_objects as go
from plotly.subplots import make_subplots

from ..feature.window import Windows
from ..feature.features import RunnerFeatureBase
from ..feature.utils import generate_features, get_feature_data
from ..feature.historic import hist_runner_features
from ..feature.config import get_features_default_configs
from .config import get_plot_feature_default_configs, get_plot_default_config
from .feature import add_feature_trace
from .orderinfo import plot_orders
from myutils import generic
import logging

active_logger = logging.getLogger(__name__)

# number of seconds to buffer when trimming record list
PROCESS_BUFFER_S = 10


def fig_to_file(fig: go.Figure, file_path, mode='a'):
    """
    write a plotly figure to a file, default mode appending to file
    """
    with generic.create_dirs(open)(file_path, mode) as f:
        f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
    active_logger.info(f'writing figure to file "{file_path}"')


def fig_historical(
        all_features_data: Dict[str, List[Dict]],
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
        display_seconds: int,
        feature_configs: Dict = None,
        feature_plot_configs: Dict = None,
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

    # use default feature configuration if not passed
    if feature_configs is None:
        feature_configs = get_features_default_configs()

    # create runner feature instances
    windows = Windows()
    features = generate_features(
        selection_id=selection_id,
        book=hist_records[0][0],
        windows=windows,
        feature_configs=feature_configs
    )

    # run feature processors on historic data
    hist_runner_features(selection_id, hist_records, windows, features)

    # create feature plotting configurations (use defaults if not passed)
    if feature_plot_configs is None:
        feature_plot_configs = get_plot_feature_default_configs()

    # use last record as first records market time can be accurate
    market_time = hist_records[-1][0].market_definition.market_time

    # if display seconds passed use offset from start time, if not just use first record
    if display_seconds:
        chart_start = market_time - timedelta(seconds=display_seconds)
        active_logger.info(f'using chart start {chart_start}, {display_seconds}s before market time')
    else:
        chart_start = hist_records[0][0].publish_time
        active_logger.info(f'using first record for chart start {chart_start}')

    # chart end is market start
    chart_end = market_time
    active_logger.info(f'using market time for chart end {chart_end}')

    # if features are using windows,
    if windows.windows:
        max_window_s = max(windows.windows.keys())
        chart_start = chart_start - timedelta(seconds=max_window_s+PROCESS_BUFFER_S)
        active_logger.info(f'setting chart start to {chart_start}, accounting for window {max_window_s}s and buffer '
                           f'{PROCESS_BUFFER_S}s')

    # trim record list
    hist_records = [r for r in hist_records if chart_start <= r[0].publish_time <= chart_end]

    # check trimmed record set not empty
    if not len(hist_records):
        active_logger.warning('trimmed records empty')
        return go.Figure()

    # get feature data from feature set
    all_features_data = {}
    get_feature_data(all_features_data, features, pre_serialize=False)

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

    fig.update_layout(title=title) , # hovermode='x')
    fig.update_xaxes({
        'rangeslider': {
            'visible': False
        },
        'range':  [
            chart_start,
            chart_end
        ],
    })
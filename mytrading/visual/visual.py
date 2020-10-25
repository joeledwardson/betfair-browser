from datetime import timedelta
from typing import List, Dict

import pandas as pd
from betfairlightweight.resources import MarketBook
from plotly import graph_objects as go

import mytrading.feature.config
import mytrading.visual
import mytrading.visual.config
from mytrading.feature import window, window as bfw, feature as bff
from .functions import get_yaxes_names, create_figure, add_feature_parent, set_figure_layout, runner_features
from mytrading.visual.orderinfo import plot_orders
from mytrading.visual.config import get_default_plot_config
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
        records: List[List[MarketBook]],
        features: Dict[str, bff.RunnerFeatureBase],
        windows: window.Windows,
        feature_plot_configs: Dict[str, Dict],
        selection_id,
        title,
        display_s=0,
        orders_df:pd.DataFrame=None):
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

    if len(records) == 0:
        active_logger.warning('records set empty')
        return go.Figure()
    # use last record as first records market time can be accurate
    market_time = records[-1][0].market_definition.market_time

    # if display seconds passed use offset from start time, if not just use first record
    if display_s:
        chart_start = market_time - timedelta(seconds=display_s)
        active_logger.info(f'using chart start {chart_start}, {display_s}s before market time')
    else:
        chart_start = records[0][0].publish_time
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
    records = [r for r in records if chart_start <= r[0].publish_time <= chart_end]

    if not len(records):
        active_logger.warning('trimmed records empty')
        return go.Figure()

    active_logger.info(f'trimmed records {len(records)}')

    # loop records and process features
    runner_features(selection_id, records, windows, features)

    # TODO - assume using default configuration
    default_plot_config = get_default_plot_config()
    y_axes_names = get_yaxes_names(feature_plot_configs, default_plot_config)
    fig = create_figure(y_axes_names)

    for feature_name, feature in features.items():
        conf = feature_plot_configs.get(feature_name, {})
        add_feature_parent(
            display_name=feature_name,
            feature=feature,
            fig=fig,
            conf=conf,
            default_plot_config=default_plot_config,
            y_axes_names=y_axes_names,
            chart_start=chart_start,
            chart_end=chart_end,
        )

    if orders_df is not None and orders_df.shape[0]:
        orders_df = orders_df[
            (orders_df.index >= market_time - timedelta(seconds=display_s)) &
            (orders_df.index <= market_time)]
        plot_orders(fig, orders_df.copy())
    set_figure_layout(fig, title, market_time, display_s)
    return fig


def generate_feature_plot(
        hist_records: List[List[MarketBook]],
        selection_id: int,
        display_seconds: int,
        title: str,
        orders_df: pd.DataFrame
) -> go.Figure:
    """create historical feature plot for a single runners based on record list, default configs and optional orders
    frame"""

    if not hist_records:
        return go.Figure()

    # create runner feature instances (use defaults)
    windows = bfw.Windows()
    features = bff.generate_features(
        selection_id=selection_id,
        book=hist_records[0][0],
        windows=windows,
        features_config=mytrading.feature.config.get_default_features_config()
    )

    # create feature plotting configurations (use defaults)
    feature_plot_configs = mytrading.visual.config.get_plot_configs(features)

    # create runner feature figure and append to html output path
    fig = fig_historical(
        records=hist_records,
        features=features,
        windows=windows,
        feature_plot_configs=feature_plot_configs,
        selection_id=selection_id,
        title=title,
        display_s=display_seconds,
        orders_df=orders_df
    )

    return fig
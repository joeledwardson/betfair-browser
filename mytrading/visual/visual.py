from datetime import timedelta
from typing import List, Dict

import pandas as pd
from betfairlightweight.resources import MarketBook
from plotly import graph_objects as go

import mytrading.feature.config
import mytrading.visual
import mytrading.visual.config
from mytrading.feature import window, window as bfw, feature as bff
from .functions import get_yaxes_names, create_figure, add_feature_parent, set_figure_layout
from mytrading.visual.orderinfo import plot_orders
from mytrading.visual.config import get_default_plot_config
from myutils import generic
import logging

active_logger = logging.getLogger(__name__)


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
        print('records set empty')
        return go.Figure()

    recs = []

    for i in range(len(records)):
        new_book = records[i][0]
        recs.append(new_book)
        windows.update_windows(recs, new_book)

        runner_index = next((i for i, r in enumerate(new_book.runners) if r.selection_id == selection_id), None)
        if runner_index is not None:
            for feature in features.values():
                feature.process_runner(recs, new_book, windows, runner_index)

    default_plot_config = get_default_plot_config()
    y_axes_names = get_yaxes_names(feature_plot_configs, default_plot_config)
    fig = create_figure(y_axes_names)

    # use last record as first records market time can be accurate
    market_time = records[-1][0].market_definition.market_time

    if display_s:
        chart_start = market_time - timedelta(seconds=display_s)
    else:
        chart_start = records[0][0].publish_time
    chart_end = market_time

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
    fig = mytrading.visual.visual.fig_historical(
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
from betfairlightweight.resources import MarketBook
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from datetime import timedelta
from typing import List, Dict
from datetime import datetime
import logging
from myutils.timing import decorator_timer
from mytrading.feature.feature import RunnerFeatureBase
from mytrading.feature.window import Windows
from .dataprocessors import process_plotly_data
from .figprocessors import post_process_figure

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


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


@decorator_timer
def runner_features(
        selection_id: int,
        records: List[List[MarketBook]],
        windows: Windows,
        features: Dict[str, RunnerFeatureBase]):
    """
    process historical records with a set of features for a selected runner
    """
    feature_records = []
    for i in range(len(records)):
        new_book = records[i][0]
        feature_records.append(new_book)
        windows.update_windows(feature_records, new_book)

        runner_index = next((i for i, r in enumerate(new_book.runners) if r.selection_id == selection_id), None)
        if runner_index is not None:
            for feature in features.values():
                feature.process_runner(feature_records, new_book, windows, runner_index)


def add_feature_trace(
        fig: go.Figure,
        feature_name: str,
        feature: RunnerFeatureBase,
        features: Dict[str, RunnerFeatureBase],
        def_conf: Dict,
        ftr_conf: Dict,
        y_axes_names: List,
        chart_start: datetime = None,
        chart_end: datetime = None):
    """
    create trace from feature data and add to figure
    - fig: plotly figure to add traces
    - feature_name: name of feature to use on chart
    - def_conf: default plotly configuration
    - ftr_conf: plotly configuration specific to feature, if non-empty override `def_conf` values
    - y_axes_names: list of y-axes names for grid selection
    - chart_start: timestamp of plotting start time
    """

    active_logger.info(f'plotting feature: "{feature_name}"')

    # if told to ignore feature then exit
    if ftr_conf.get('ignore'):
        return

    # get default y-axis name
    def_yaxis = def_conf['y_axis']

    # get y-axis (if not exist use default) and produce grid row index (starting from 1)
    row = list(y_axes_names).index(ftr_conf.get('y_axis', def_yaxis)) + 1

    # plotly chart function, chart kwargs, trace kwargs updating with grid row and (single column)
    chart_func = ftr_conf.get('chart', def_conf['chart'])
    chart_args = ftr_conf.get('chart_args', def_conf['chart_args'])
    trace_args = ftr_conf.get('trace_args', def_conf['trace_args'])
    trace_args.update({'col': 1, 'row': row})

    # get list of plotly data dictionary
    trace_data_lists = feature.get_plotly_data()

    value_processors = ftr_conf.get('value_processors', [])

    for trace_data in trace_data_lists:
        trace_data = process_plotly_data(trace_data, features, value_processors)

        # check there is data
        if not('x' in trace_data and len(trace_data['x'])):
            continue

        # if chart start datetime not passed, then set to first element
        if chart_start is None:
            chart_start = trace_data['x'][0]

        # if chart end datetime not passed, then set to last element
        if chart_end is None:
            chart_end = trace_data['x'][-1]

        # indexes of data values which are after chart start time for plotting
        indexes = [
            i for i, v in enumerate(trace_data['x'])
            if chart_start <= v <= chart_end
        ]

        # if no values are after start then abort
        if not indexes:
            continue

        index_start = min(indexes)
        index_end = max(indexes)

        # slice trace data to values within plotting range
        trace_data = {k: v[index_start:index_end] for k, v in trace_data.items()}

        # create plotly chart using feature name, trace data, kwargs and add to plotly figure
        chart = chart_func(
            name=feature_name,
            **trace_data,
            **chart_args)

        fig.add_trace(chart, **trace_args)

    # run figure post processors
    post_process_figure(fig, ftr_conf.get('fig_post_processors', []))


def add_feature_parent(
        display_name: str,
        feature: RunnerFeatureBase,
        features: Dict[str, RunnerFeatureBase],
        fig: go.Figure,
        conf: dict,
        default_plot_config: Dict,
        y_axes_names: List[str],
        chart_start: datetime = None,
        chart_end: datetime = None,
):
    """
    add a feature trace to a chart, including all its children features
    """

    # plot feature
    add_feature_trace(
        fig=fig,
        feature_name=display_name,
        feature=feature,
        features=features,
        def_conf=default_plot_config,
        y_axes_names=y_axes_names,
        ftr_conf=conf,
        chart_start=chart_start,
        chart_end=chart_end,
    )

    # get sub features config if exist
    sub_configs = conf.get('sub_features', {})

    # loop sub features
    for sub_name, sub_feature in feature.sub_features.items():

        # get sub-feature specific configuration
        sub_conf = sub_configs.get(sub_name, {})

        # create display name by using using a dot (.) between parent and sub feature names
        sub_display_name = '.'.join([display_name, sub_name])

        add_feature_parent(
            display_name=sub_display_name,
            feature=sub_feature,
            features=features,
            fig=fig,
            conf=sub_conf,
            default_plot_config=default_plot_config,
            y_axes_names=y_axes_names,
            chart_start=chart_start,
            chart_end=chart_end
        )


def set_figure_layout(fig: go.Figure, title: str, market_time: datetime, display_s: int):
    """
    set plotly figure layout with a title, limit x axis from start time minus display seconds
    """

    fig.update_layout(title=title) , # hovermode='x')
    fig.update_xaxes({
        'rangeslider': {
            'visible': False
        },
        'range':  [
            market_time - timedelta(seconds=display_s),
            market_time
        ],
    })

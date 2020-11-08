import plotly.graph_objects as go
from typing import List, Dict
from datetime import datetime
import logging
from .processors.dataprocessors import process_plotly_data
from .processors.figprocessors import post_process_figure

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def add_feature_trace(
        fig: go.Figure,
        feature_name: str,
        all_features_data: Dict[str, Dict[str, List]],
        default_config: Dict,
        feature_config: Dict,
        y_axes_names: List,
        chart_start: datetime = None,
        chart_end: datetime = None):
    """
    create trace from feature data and add to figure
    - fig: plotly figure to add traces
    - feature_name: name of feature to use on chart, and to index feature data
    - def_conf: default plotly configuration
    - ftr_conf: plotly configuration specific to feature, if non-empty override `def_conf` values
    - y_axes_names: list of y-axes names for grid selection
    - chart_start: timestamp of plotting start time
    """

    active_logger.info(f'plotting feature: "{feature_name}"')

    # if told to ignore feature then exit
    if feature_config.get('ignore'):
        return

    # get default y-axis name
    def_yaxis = default_config['y_axis']

    # get y-axis (if not exist use default) and produce grid row index (starting from 1)
    row = list(y_axes_names).index(feature_config.get('y_axis', def_yaxis)) + 1

    # plotly chart function, chart kwargs, trace kwargs updating with grid row and (single column)
    chart_name = feature_config.get('chart', default_config['chart'])
    chart_args = feature_config.get('chart_args', default_config['chart_args'])
    trace_args = feature_config.get('trace_args', default_config['trace_args'])
    trace_args.update({'col': 1, 'row': row})

    # get list of plotly data dictionary
    trace_data_lists = all_features_data[feature_name]

    value_processors = feature_config.get('value_processors', [])

    for trace_data in trace_data_lists:
        trace_data = process_plotly_data(trace_data, all_features_data, value_processors)

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

        # get plotly chart function from chart function name
        chart_func = getattr(go, chart_name)

        # create plotly chart using feature name, trace data, kwargs and add to plotly figure
        chart = chart_func(
            name=feature_name,
            **trace_data,
            **chart_args)

        fig.add_trace(chart, **trace_args)

    # run figure post processors
    post_process_figure(fig, feature_config.get('fig_post_processors', []))



#
# def add_feature_parent(
#         feature_name: str,
#         all_features_data: Dict[str, List[Dict]],
#         fig: go.Figure,
#         conf: dict,
#         default_plot_config: Dict,
#         y_axes_names: List[str],
#         chart_start: datetime = None,
#         chart_end: datetime = None,
# ):
#     """
#     add a feature trace to a chart, including all its children features
#     """
#
#     # plot feature
#     add_feature_trace(
#         fig=fig,
#         feature_name=feature_name,
#         all_features_data=all_features_data,
#         def_conf=default_plot_config,
#         y_axes_names=y_axes_names,
#         ftr_conf=conf,
#         chart_start=chart_start,
#         chart_end=chart_end,
#     )
#
#     # get sub features config if exist
#     sub_configs = conf.get('sub_features', {})
#
#     # loop sub features
#     for sub_name, sub_feature in feature.sub_features.items():
#
#         # get sub-feature specific configuration
#         sub_conf = sub_configs.get(sub_name, {})
#
#         # create display name by using using a dot (.) between parent and sub feature names
#         sub_display_name = '.'.join([display_name, sub_name])
#
#         add_feature_parent(
#             display_name=sub_display_name,
#             feature=sub_feature,
#             features=features,
#             fig=fig,
#             conf=sub_conf,
#             default_plot_config=default_plot_config,
#             y_axes_names=y_axes_names,
#             chart_start=chart_start,
#             chart_end=chart_end
#         )



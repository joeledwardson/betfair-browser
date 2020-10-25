from plotly import graph_objects as go
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from datetime import timedelta
from typing import List, Dict
from datetime import datetime
import logging
import pandas as pd
from mytrading.feature.feature import RunnerFeatureBase

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def values_resampler(df: pd.DataFrame, n_seconds, sampling_function='last') -> pd.DataFrame:
    """
    resample 'df' DataFrame for 'n_seconds', using last value each second and forward filling
    can override default sampling function 'last' with `sampling_function` arg
    """
    rule = f'{n_seconds}S'
    return df.resample(rule).apply(sampling_function).fillna(method='ffill') if df.shape[0] else df


def color_text_formatter_percent(value, name, n_decimals=0) -> str:
    """
    format value with name to percentage with 'n_decimals' dp
    """
    return f'{name}: {value:.{n_decimals}%}'


def color_text_formatter_decimal(value, name, n_decimals=2, prefix='') -> str:
    """
    format value with name to decimal with 'n_decimals' dp
    """
    return f'{name}: {prefix}{value:.{n_decimals}f}'


def remove_duplicates(sr: pd.Series) -> pd.Series:
    """
    remove duplicates from series with datetime index keeping last value
    """
    return sr[~sr.index.duplicated(keep='last')]


def plotly_data_to_series(data: dict) -> pd.Series:
    """
    convert 'data' x-y plotly values (dict with 'x' and 'y' indexed list values) to pandas series where index is 'x'
    """
    return pd.Series(data['y'], index=data['x'])


def plotly_set_attrs(
        vals: Dict,
        feature_configs: List[Dict],
) -> pd.DataFrame:
    """
    For a given dictionary 'vals' of plotly data containing 'x' and 'y' lists of values, set additional dictionary
    attributes to be accepted by a plotly chart function

    'feature_configs' dictionary specifies what features to use as additional attributes and how to process them
    - list of feature configuration dictionaries:
    -   'feature': RunnerFeatureBase() instance to get values from (only first index from values list is used!)
    -   'processors': list of processor(data: dict) functions to run on data retrieved from feature
    -   'attr formatters': dictionary of:
    -       key: attribute name to set in plotly dictionary
    -       value: formatter(data: dict) to format data into visualisation form

    example of 'feature_configs':
    """

    # have to remove duplicate datetime indexes from each series or pandas winges when trying to make a dataframe
    sr_vals = plotly_data_to_series(vals)
    sr_vals = remove_duplicates(sr_vals)

    df_data = {
        'y': sr_vals,
    }

    for cnf in feature_configs:

        # get data from feature to be used as color in plot (assume single plotting element)
        data = cnf['feature'].get_plotly_data()[0]

        # run processors on color data (if not empty)
        for processor in cnf['processors']:
            data = processor(data)

        # check has x and y values
        if 'y' in data and len(data['y']) and 'x' in data and len(data['x']):

            # create series and remove duplicates from color data
            sr = pd.Series(data['y'], index=data['x'])
            sr = remove_duplicates(sr)

            for df_key, formatter in cnf['attr formatters'].items():
                df_data[df_key] = sr.apply(formatter)

    df = pd.DataFrame(df_data)
    df = df.fillna(method='ffill')
    return df


def plotly_df_to_data(df: pd.DataFrame) -> Dict:
    """
    convert dataframe to dictionary (assuming columns are appropriate for plotly chart arg) and use index for 'x' vals
    """
    values = df.to_dict(orient='list')
    values.update({'x': df.index})
    return values


def plotly_series_to_data(sr: pd.Series) -> Dict:
    """
    convert series to dictionary with 'x' and 'y'
    """
    return {
        'x': sr.index,
        'y': sr.to_list()
    }


def plotly_regression(vals: Dict) -> Dict:
    """
    convert returned values dict from 'RunnerFeatureRegression' feature into plotly compatible dict with 'x',
    'y' and 'text'
    """
    txt_rsqaured = f'rsquared: {vals["rsquared"]:.2f}'
    return {
        'x': vals['dts'],
        'y': vals['predicted'],
        'text': [txt_rsqaured for x in vals['dts']]
    }


def plotly_group(fig: go.Figure, name: str, group_name: str):
    """
    group a set of plotly traces with a unified name to a single legend
    """
    # filter to traces with name
    for i, trace in enumerate([t for t in fig.data if t['name']==name]):
        # show legend on first trace but ignore others
        if i == 0:
            trace['showlegend'] = True
        else:
            trace['showlegend'] = False
        # set all trace group names the same
        trace['legendgroup'] = group_name


def get_yaxes_names(feature_plot_configs: dict, _default_plot_configs: dict) -> List[str]:
    """get list of yaxis names from default configuration and list of feature configurations"""

    def_yaxis = _default_plot_configs['y_axis']
    return list(set(
        [def_yaxis] + [c.get('y_axis', def_yaxis)
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


def add_feature_trace(
        fig: go.Figure,
        feature_name: str,
        feature: RunnerFeatureBase,
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
    
    for trace_data in trace_data_lists:
    
        # only do processors if NOT: (check value is dict) and all dict lists are empty (pandas functions will fail)
        if not(
                type(trace_data) is dict and 
                all([
                    bool(v) == False 
                    for v in trace_data.values()
                    if type(v) is list
                ])
        ):
            for processor in ftr_conf.get('value_processors', []):
                trace_data = processor(trace_data)

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

    # if exist, run figure post processor
    if 'fig_post_processor' in ftr_conf:
        ftr_conf['fig_post_processor'](fig)


def add_feature_parent(
        display_name: str,
        feature: RunnerFeatureBase,
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

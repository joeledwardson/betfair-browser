from plotly.subplots import make_subplots
import plotly.graph_objects as go
from myutils import generic, bf_feature, bf_window, timing
import pandas as pd
from datetime import timedelta
from typing import List, Dict
from betfairlightweight.resources.bettingresources import MarketBook
from functools import partial
from datetime import datetime





# resample 'df' DataFrame for 'n_seconds', using last value each second and forward filling
def values_resampler(df: pd.DataFrame, n_seconds, sampling_function='last') -> pd.DataFrame:
    rule = f'{n_seconds}S'
    return df.resample(rule).apply(sampling_function).fillna(method='ffill') if df.shape[0] else df


# format value with name to percentage with 'n_decimals' dp
def color_text_formatter_percent(name, value, n_decimals=0):
    return f'{name}: {value:.{n_decimals}%}'


# format value with name to decimal with 'n_decimals' dp
def color_text_formatter_decimal(name, value, n_decimals=2):
    return f'{name}: {value:.{n_decimals}f}'


# remove duplicates from series with datetime index keeping last value
def remove_duplicates(sr: pd.Series):
    return sr[~sr.index.duplicated(keep='last')]


# convert x-y plotly values to dataframe
def plotly_data_to_series(data: dict) -> pd.Series:
    return pd.Series(data['y'], index=data['x'])


# add color to plotly 'vals' (must have 'x' and 'y' components) from 'color_feature' feature (must also have 'x' and 
# 'y' components) into dataframe, where color forms 'marker_color' column, formatted color values with 
# 'color_feature_name' form 'text' column
def plotly_set_color(
        vals: Dict,
        color_feature: bf_feature.RunnerFeatureBase,
        color_feature_name: str,
        color_feature_processors: List,
        color_text_fmt=color_text_formatter_decimal
) -> pd.DataFrame:

    # have to remove duplicate datetime indexes from each series or pandas winges when trying to make a dataframe
    sr_vals = plotly_data_to_series(vals)
    sr_vals = remove_duplicates(sr_vals)

    # get data from feature to be used as color in plot (assume single plotting element)
    color_data = color_feature.get_plotly_data()[0]

    # run processors on color data (if not empty)
    if color_data['x']:
        for processor in color_feature_processors:
            color_data = processor(color_data)

    # create series and remove duplicates from color data
    sr_color = pd.Series(color_data['y'], index=color_data['x'])
    sr_color = remove_duplicates(sr_color)

    # create series of text annotations
    text_data = [color_text_fmt(color_feature_name, v) for v in color_data['y']]
    sr_text = pd.Series(text_data, index=color_data['x'])
    sr_text = remove_duplicates(sr_text)

    df = pd.DataFrame({
        'y': sr_vals,
        'marker_color': sr_color,
        'text': sr_text
    })
    df = df.fillna(method='ffill')
    return df


# convert dataframe to dictionary (assuming columns are appropriate for plotly chart arg) and use index for 'x' vals
def plotly_df_to_data(df: pd.DataFrame) -> Dict:
    values = df.to_dict(orient='list')
    values.update({'x': df.index})
    return values


# convert series to dictionary of 'x' and 'y'
def plotly_series_to_data(sr: pd.Series) -> Dict:
    return {
        'x': sr.index,
        'y': sr.to_list()
    }


# convert returned data from 'RunnerFeatureRegression' feature into plotly compatible arguemnts
def plotly_regression(vals: Dict):
    txt_rsqaured = f'rsquared: {vals["rsquared"]:.2f}'
    return {
        'x': vals['dts'],
        'y': vals['predicted'],
        'text': [txt_rsqaured for x in vals['dts']]
    }


# default plotly chart configurations for plotting features
# configs include:
#   'chart': plotly chart function
#   'chart_args': dictionary of plotly chart arguments
#   'trace_args': dictionary of arguments used when plotly trace added to figure
#   'y_axis': name of y-axis, used as a set to distinguish different y-axes on subplots (just used to differentiate
#   between subplots, name doesn't actually appear on axis)
default_plot_configs = {
    'chart': go.Scatter,
    'chart_args': {
        'mode': 'lines'
    },
    'trace_args': {},
    'y_axis': 'odds',
}


# dict of {feature name: plotly config dict}, for plotting features, where feature names match those from
# get_default_features()
# configs include:
#   'ignore': True if chart not to be displayed (i.e. if used as color in another chart don't need)
#   'chart': override default plotly chart function
#   'chart_args': override default chart arguments
#   'trace_args': override feault trace arguments
#   'y_axis': override default y-axis
#   'value_processors': list of functions called on feature.get_data() outputs before passed to chart constructor
def get_default_feature_plot_config(features, ltp_diff_opacity=0.4, ltp_marker_opacity=0.5):
    return {
        'best back': {
            'chart_args': {
                'visible': 'legendonly',
            }
        },
        'best lay': {
            'chart_args': {
                'visible': 'legendonly',
            }
        },
        'wom': {
            'ignore': True,
        },
        'book split': {
            'ignore': True,
        },
        'ltp diff': {
            'chart': go.Bar,
            'chart_args': {
                'opacity': ltp_diff_opacity,
                'width': 1000,
                'offset': -1000,
            },
            'trace_args': {
                'secondary_y': True
            },
            'value_processors': [
                partial(
                    plotly_set_color,
                    color_feature=features['wom'],
                    color_feature_name='weight of money',
                    color_text_fmt=color_text_formatter_decimal,
                    color_feature_processors=[
                        plotly_data_to_series,
                        partial(
                            values_resampler,
                            n_seconds=features['ltp diff'].window_s,
                            sampling_function='mean'
                        ),
                        plotly_series_to_data
                    ],
                ),
                partial(
                    values_resampler,
                    n_seconds=features['ltp diff'].window_s
                ),
                plotly_df_to_data
                ,
            ],
        },
        'ltp': {
            'chart_args': {
            #     'mode': 'lines+markers',
                'marker': {
                    'opacity': ltp_marker_opacity,
                },
            },
            # 'value_processors': [
            #     partial(
            #         plotly_set_color,
            #         color_feature=features['wom'],
            #         color_feature_name='Weight of money',
            #         color_feaure_
            #     ),
            #     plotly_df_to_data
            # ],
        },
        'best back regression': {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [
                plotly_regression
            ]
        },
        'best lay regression': {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [
                plotly_regression
            ]
        },
    }


# get list of yaxis names from default configuration and list of feature configurations
def get_yaxes_names(feature_plot_configs, _default_plot_configs) -> List[str]:
    def_yaxis = _default_plot_configs['y_axis']
    return list(set(
        [def_yaxis] + [c.get('y_axis', def_yaxis)
                       for c in feature_plot_configs.values()]
    ))


# create chart with subplots based on 'y_axis' properties of feature plot configurations
def create_figure(y_axes_names, vertical_spacing=0.05) -> go.Figure:

    n_cols = 1
    n_rows = len(y_axes_names)

    return make_subplots(
        cols=n_cols,
        rows=n_rows,
        shared_xaxes=True,
        specs=[[{'secondary_y': True} for y in range(n_cols)] for x in range(n_rows)],
        vertical_spacing=vertical_spacing)


# create trace from feature data and add to figure
def add_feature_trace(
        fig: go.Figure,
        feature_name: str,
        feature: bf_feature.RunnerFeatureBase,
        _default_plot_configs: Dict,
        y_axes_names: List,
        conf: Dict,
        chart_start: datetime):

    if conf.get('ignore'):
        return

    def_yaxis = _default_plot_configs['y_axis']
    row = list(y_axes_names).index(conf.get('y_axis', def_yaxis)) + 1

    chart_func = conf.get('chart',      _default_plot_configs['chart'])
    chart_args = conf.get('chart_args', _default_plot_configs['chart_args'])
    trace_args = conf.get('trace_args', _default_plot_configs['trace_args'])
    trace_args.update({'col': 1, 'row': row})

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
            for processor in conf.get('value_processors', []):
                trace_data = processor(trace_data)
    
        indexes = [i for i, v in enumerate(trace_data['x']) if v >= chart_start]
        index_start = min(indexes) if indexes else 0
    
        trace_data = {k: v[index_start:] for k, v in trace_data.items()}
    
        chart = chart_func(
            name=feature_name,
            **trace_data,
            **chart_args)
    
        fig.add_trace(chart, **trace_args)


# set figure layout
def set_figure_layout(fig, title, market_time, display_s):
    fig.update_layout(title=title)
    fig.update_xaxes({
        'rangeslider': {
            'visible': False
        },
        'range':  [
            market_time - timedelta(seconds=display_s),
            market_time
        ],
    })


# create figure using default features for historical record list and a selected runner ID
def fig_historical(records: List[List[MarketBook]], selection_id, title, display_s=90):

    if len(records) == 0:
        print('records set empty')
        return go.Figure()

    windows = bf_window.Windows()
    features = bf_feature.get_default_features(selection_id, records[0][0], windows)
    feature_plot_configs = get_default_feature_plot_config(features)

    recs = []

    for i in range(len(records)):
        new_book = records[i][0]
        recs.append(new_book)
        windows.update_windows(recs, new_book)

        runner_index = next((i for i, r in enumerate(new_book.runners) if r.selection_id == selection_id), None)
        if runner_index is not None:
            for feature in features.values():
                feature.process_runner(recs, new_book, windows, runner_index)

    y_axes_names = get_yaxes_names(feature_plot_configs, default_plot_configs)
    fig = create_figure(y_axes_names)

    market_time = records[0][0].market_definition.market_time
    for feature_name, feature in features.items():
        conf = feature_plot_configs.get(feature_name, {})
        add_feature_trace(
            fig=fig,
            feature_name=feature_name,
            feature=feature,
            _default_plot_configs=default_plot_configs,
            y_axes_names=y_axes_names,
            conf=conf,
            chart_start=market_time-timedelta(seconds=display_s)
        )

    set_figure_layout(fig, title, market_time, display_s)
    return fig


def fig_to_file(fig: go.Figure, file_path, mode='a'):
    with generic.create_dirs(open)(file_path, mode) as f:
        f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))

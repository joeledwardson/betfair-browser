from plotly.subplots import make_subplots
import plotly.graph_objects as go
from datetime import timedelta
from typing import List, Dict
from betfairlightweight.resources.bettingresources import MarketBook
from functools import partial
from datetime import datetime
import logging
import pandas as pd

from myutils import generic
from mytrading import bf_feature, bf_window

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)



def get_plot_configs(
        features: Dict[str, bf_feature.RunnerFeatureBase],
        ltp_diff_opacity=0.4,
        ltp_marker_opacity=0.5) -> Dict[str, Dict]:
    """
    get dict of {feature name: plotly config dict}, for plotting features, where feature names match those from
    bf_feature.get_default_features()

    dict configurations include:
    - 'ignore': True if chart not to be displayed (i.e. if used as color in another chart don't need)
    - 'chart': override default plotly chart function
    - 'chart_args': override default chart arguments
    - 'trace_args': override default trace arguments
    - 'y_axis': override default y-axis name
    - 'value_processors': list of functions called on feature.get_data() outputs before passed to chart constructor
    - 'fig_post_processor': function(figure) to be called after creation for any manual updates to plotly figure
    """

    # name of back regression feature
    back_regression = 'best back regression'

    # name of lay regression feature
    lay_regression = 'best lay regression'

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
                'width': 1000,  # 1 seconds width of bars
                'offset': -1000,  # end of bar to be aligned with timestamp
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
        back_regression: {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [
                plotly_regression
            ],
            'fig_post_processor': partial(
                plotly_group,
                name=back_regression,
                group_name=back_regression
            )
        },
        lay_regression: {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [
                plotly_regression
            ],
            'fig_post_processor': partial(
                plotly_group,
                name=lay_regression,
                group_name=lay_regression
            )
        },
    }


def get_default_plot_config() -> dict:
    """
    get default plotly chart configurations dict for plotting features
    configuration includes keys:
    - 'chart': plotly chart function
    - 'chart_args': dictionary of plotly chart arguments
    - 'trace_args': dictionary of arguments used when plotly trace added to figure
    - 'y_axis': name of y-axis, used as a set to distinguish different y-axes on subplots (just used to
    differentiate between subplots, name doesn't actually appear on axis)
    """
    return {
        'chart': go.Scatter,
        'chart_args': {
            'mode': 'lines'
        },
        'trace_args': {},
        'y_axis': 'odds',
    }


def values_resampler(df: pd.DataFrame, n_seconds, sampling_function='last') -> pd.DataFrame:
    """
    resample 'df' DataFrame for 'n_seconds', using last value each second and forward filling
    can override default sampling function 'last' with `sampling_function` arg
    """
    rule = f'{n_seconds}S'
    return df.resample(rule).apply(sampling_function).fillna(method='ffill') if df.shape[0] else df


def color_text_formatter_percent(name, value, n_decimals=0) -> str:
    """
    format value with name to percentage with 'n_decimals' dp
    """
    return f'{name}: {value:.{n_decimals}%}'


def color_text_formatter_decimal(name, value, n_decimals=2) -> str:
    """
    format value with name to decimal with 'n_decimals' dp
    """
    return f'{name}: {value:.{n_decimals}f}'


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


def plotly_set_color(
        vals: Dict,
        color_feature: bf_feature.RunnerFeatureBase,
        color_feature_name: str,
        color_feature_processors: List,
        color_text_fmt=color_text_formatter_decimal
) -> pd.DataFrame:
    """
    add color to plotly 'vals' (must have 'x' and 'y' components) from 'color_feature' feature (must also have 'x' and
    'y' components) into dataframe, where color forms 'marker_color' column, formatted color values with
    'color_feature_name' form 'text' column
    """

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
        feature: bf_feature.RunnerFeatureBase,
        def_conf: Dict,
        ftr_conf: Dict,
        y_axes_names: List,
        chart_start: datetime):
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

        # indexes of data values which are after chart start time for plotting
        indexes = [i for i, v in enumerate(trace_data['x']) if v >= chart_start]

        # if no values are after start then abore
        if not indexes:
            continue

        index_start = min(indexes)

        # slice trace data to values within plotting range
        trace_data = {k: v[index_start:] for k, v in trace_data.items()}

        # create plotly chart using feature name, trace data, kwargs and add to plotly figure
        chart = chart_func(
            name=feature_name,
            **trace_data,
            **chart_args)

        fig.add_trace(chart, **trace_args)

    # if exist, run figure post processor
    if 'fig_post_processor' in ftr_conf:
        ftr_conf['fig_post_processor'](fig)


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


def plot_orders(fig: go.Figure, orders_df: pd.DataFrame):
    """
    add dataframe of order information to plot

    orders dataframe is expected to have
    - datetime timestamp as index
    - 'msg' column for string update
    - 'display_odds' column for price to display on chart
    """

    for i, (trade_id, df) in enumerate(orders_df.groupby(['trade_id'])):

        # so can see annotations for overlapping points need to combine text (use last instance for display odds)
        msgs = df.groupby(df.index)['msg'].apply(lambda x: '<br>'.join(x))
        display_odds = df.groupby(df.index)['display_odds'].last()
        df = pd.concat([msgs, display_odds], axis=1)

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['display_odds'],
            text=df['msg'],
            name='order info',
            legendgroup='order info',
            showlegend=(i == 0),
        ))


def fig_historical(
        records: List[List[MarketBook]],
        features: Dict[str, bf_feature.RunnerFeatureBase],
        windows: bf_window.Windows,
        feature_plot_configs: Dict[str, Dict],
        selection_id,
        title,
        display_s=90,
        orders_df:pd.DataFrame=None):
    """
    create figure using default features for historical record list and a selected runner ID
    - records: list of historical records
    - features: dict of {feature name: feature instance} to apply
    - feature_plot_configs: dict of {feature name: feature plot config} to apply when plotting each feature
    - selection_id: id of runner
    - title: title to apply to chart
    - display_s: number of seconds before start time to display chart for
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

    market_time = records[0][0].market_definition.market_time
    chart_start = market_time - timedelta(seconds=display_s)

    def _plot_feature(display_name, feature, conf):

        # plot feature
        add_feature_trace(
            fig=fig,
            feature_name=display_name,
            feature=feature,
            def_conf=default_plot_config,
            y_axes_names=y_axes_names,
            ftr_conf=conf,
            chart_start=chart_start
        )

        # get sub features config if exist
        sub_configs = conf.get('sub_features', {})

        # loop sub features
        for sub_name, sub_feature in feature.sub_features:

            # get sub-feature specific configuration
            sub_conf = sub_configs.get(sub_name)

            # create display name by using using a dot (.) between parent and sub feature names
            sub_display_name = '.'.join([display_name, sub_name])
            _plot_feature(sub_display_name, sub_feature, sub_conf)

    for feature_name, feature in features.items():
        conf = feature_plot_configs.get(feature_name, {})
        _plot_feature(feature_name, feature, conf)

    if orders_df is not None and orders_df.shape[0]:
        orders_df = orders_df[
            (orders_df.index >= market_time - timedelta(seconds=display_s)) &
            (orders_df.index <= market_time)]
        plot_orders(fig, orders_df.copy())
    set_figure_layout(fig, title, market_time, display_s)
    return fig


def fig_to_file(fig: go.Figure, file_path, mode='a'):
    """
    write a plotly figure to a file, default mode appending to file
    """
    with generic.create_dirs(open)(file_path, mode) as f:
        f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
    active_logger.info(f'writing figure to file "{file_path}"')

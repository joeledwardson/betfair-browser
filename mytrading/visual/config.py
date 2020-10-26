from functools import partial
from typing import Dict

from plotly import graph_objects as go

from mytrading.feature import feature
from mytrading.visual.functions import plotly_set_attrs, color_text_formatter_decimal, plotly_data_to_series, \
    values_resampler, plotly_series_to_data, plotly_df_to_data, plotly_regression, plotly_group, plotly_pricesize_display

# name of back regression feature
BACK_REGRESSION_NAME = 'best back regression'

# name of lay regression feature
LAY_REGRESSION_NAME = 'best lay regression'


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


def get_plot_configs(
        features: Dict[str, feature.RunnerFeatureBase],
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
    - 'sub_features': dict of {name: configuration} sub_feature
    """


    return {
        'best back': {
            'chart_args': {
                'visible': 'legendonly',
            },
            'value_processors': [
                partial(plotly_set_attrs,
                        feature_configs=[{
                            'feature': features['back ladder'],
                            'processors': [],
                            'attr formatters': {
                                'text': lambda v: '<br>'.join(
                                    f'price: {ps["price"]}, size: {ps["size"]}' for ps in v
                                ),
                            }
                        }],
                ),
                plotly_df_to_data,
            ]
        },
        'best lay': {
            'chart_args': {
                'visible': 'legendonly',
            }
        },
        'back ladder': {
            'ignore': True,
        },
        'lay ladder': {
            'ignore': True,
        },
        'wom': {
            'ignore': True,
        },
        'book split': {
            'ignore': True,
        },
        'tv': {
            'ignore': True,
        },
        'ltp': {
            'chart_args': {
                'mode': 'lines+markers'
            },
            # 'marker': {
            #     'opacity': ltp_marker_opacity,
            # # },
            'value_processors': [
                partial(plotly_set_attrs,
                        feature_configs=[{
                            'feature': features['tv'],
                            'processors': [],
                            'attr formatters': {
                                'text': partial(color_text_formatter_decimal,
                                                name='traded vol',
                                                prefix='£'),
                            }
                        }],
                ),
                plotly_df_to_data,
            ],
        },
        'ltp diff': {
            'chart': go.Bar,
            'chart_args': {
                # default plotly colours go white, so use a green to red with grey 0 scale
                'marker': {
                    'colorscale': [[0, 'rgb(250,50,50)'], [1, 'rgb(50,250,50)']],
                    'cmid': 0,
                },
                'opacity': ltp_diff_opacity,
                'width': 1000,  # 1 seconds width of bars
                'offset': -1000,  # end of bar to be aligned with timestamp
            },
            'trace_args': {
                'secondary_y': True
            },
            'value_processors': [
                partial(plotly_set_attrs,
                        feature_configs=[{
                            'feature': features['wom'],
                            'processors': [
                                plotly_data_to_series,
                                partial(values_resampler,
                                        n_seconds=features['ltp diff'].window_s,
                                        sampling_function='mean'),
                                plotly_series_to_data
                            ],
                            'attr formatters': {
                                'marker_color': lambda x:x,
                                'text': partial(color_text_formatter_decimal,
                                                name='weight of money',
                                                prefix='£'),
                            }
                        }],),
                partial(values_resampler,
                        n_seconds=features['ltp diff'].window_s),
                plotly_df_to_data,
            ],
        },
        BACK_REGRESSION_NAME: {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [
                plotly_regression
            ],
            'fig_post_processor': partial(
                plotly_group,
                name=BACK_REGRESSION_NAME,
                group_name=BACK_REGRESSION_NAME
            )
        },
        LAY_REGRESSION_NAME: {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [
                plotly_regression
            ],
            'fig_post_processor': partial(
                plotly_group,
                name=LAY_REGRESSION_NAME,
                group_name=LAY_REGRESSION_NAME
            )
        },
        'ltp min': {
            'sub_features': {
                'delay': {
                    'chart_args': {
                        'visible': 'legendonly',
                    }
                }
            }
        },
        'ltp max': {
            'sub_features': {
                'delay': {
                    'chart_args': {
                        'visible': 'legendonly',
                    }
                }
            }
        }
    }
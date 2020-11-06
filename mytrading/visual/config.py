from typing import Dict
from plotly import graph_objects as go

# name of back regression feature
BACK_REGRESSION_NAME = 'best back regression'

# name of lay regression feature
LAY_REGRESSION_NAME = 'best lay regression'


def get_plot_default_config() -> dict:
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


def get_plot_feature_default_configs(
        ltp_diff_opacity=0.4,
        ltp_diff_s=1
) -> Dict[str, Dict]:
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
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'back ladder',
                        'feature_value_processors': [{
                            'name': 'plotly_pricesize_display'
                        }],
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_fillna',
            }, {
                'name': 'plotly_df_to_data',
            }],
        },
        'best lay': {
            'chart_args': {
                'visible': 'legendonly',
            },
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'lay ladder',
                        'feature_value_processors': [{
                            'name': 'plotly_pricesize_display'
                        }],
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_fillna',
            }, {
                'name': 'plotly_df_to_data',
            }],
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
        'ltp': {
            'chart_args': {
                'mode': 'lines+markers'
            },
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'tv',
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_fillna',
            }, {
                'name': 'plotly_df_formatter',
                'kwargs': {
                    'formatter_name': 'formatter_decimal',
                    'df_column': 'text',
                    'formatter_kwargs': {
                        'name': 'traded vol',
                        'prefix': '£',
                    }
                }
            },{
                'name': 'plotly_df_to_data',
            }],
        },
        'ltp.previous value': {
            'chart_args': {
                'visible': 'legendonly',
            },
        },
        'ltp diff': {
            'ignore': True,
        },
        'tv': {
            'chart': go.Bar,
            'chart_args': {
                'marker': {
                    'colorscale': [
                        [0, 'rgb(250,50,50)'],
                        [1, 'rgb(50,250,50)']
                    ],  # default plotly colours go white, so use a green to red scale
                    'cmid': 0,  # with grey 0 scale
                },
                'opacity': ltp_diff_opacity,
                'width': 1000,  # 1 seconds width of bars
                'offset': 0,  # end of bar to be aligned with timestamp
            },
            'trace_args': {
                'secondary_y': True
            },
            'value_processors': [{
                'name': 'plotly_data_to_series'
            }, {
                'name': 'plotly_df_diff'
            }, {
                'name': 'plotly_series_to_data'
            }, {
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'wom',
                        'attr_names': ['text', 'marker_color'],
                    }],
                },
            }, {
                'name': 'plotly_values_resampler',
                'kwargs': {
                    'n_seconds': ltp_diff_s,
                    'agg_function': {
                        'y': 'sum',
                        'text': 'mean',
                        'marker_color': 'mean',
                    }
                }
            }, {
                'name': 'plotly_df_formatter',
                'kwargs': {
                    'formatter_name': 'formatter_decimal',
                    'df_column': 'text',
                    'formatter_kwargs': {
                        'name': 'weight of money',
                        'prefix': '£',
                    }
                },
            },{
                'name': 'plotly_df_to_data'
            }],
        },
        BACK_REGRESSION_NAME: {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [{
                'name': 'plotly_regression'
            }],
            'fig_post_processors': [{
                'name': 'plotly_group',
                'kwargs': {
                    'name': BACK_REGRESSION_NAME,
                    'group_name': BACK_REGRESSION_NAME,
                }
            }],
        },
        LAY_REGRESSION_NAME: {
            'chart_args': {
                'showlegend': False
            },
            'value_processors': [{
                'name': 'plotly_regression',
            }],
            'fig_post_processors': [{
                'name': 'plotly_group',
                'kwargs': {
                    'name': LAY_REGRESSION_NAME,
                    'group_name': LAY_REGRESSION_NAME,
                }
            }],
        },
        # 'ltp min': {
        #     'sub_features': {
        #         'delay': {
        #             'chart_args': {
        #                 'visible': 'legendonly',
        #             }
        #         }
        #     }
        # },
        # 'ltp max': {
        #     'sub_features': {
        #         'delay': {
        #             'chart_args': {
        #                 'visible': 'legendonly',
        #             }
        #         }
        #     }
        # }
    }
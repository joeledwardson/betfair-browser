from typing import Dict


def get_scalp_plot_configs(ltp_diff_opacity, ltp_diff_s) -> Dict:
    return {
        'back ladder': {
            'ignore': True,
        },
        'lay ladder': {
            'ignore': True,
        },
        'spread': {
            'ignore': True,
        },
        'wom': {
            'ignore': True,
        },
        'best back': {
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'back ladder',
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_formatter',
                'kwargs': {
                    'formatter_name': 'formatter_pricesize',
                    'df_column': 'text',
                }
            }, {
                'name': 'plotly_df_to_data',
            }],
        },
        'best lay': {
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'lay ladder',
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_formatter',
                'kwargs': {
                    'formatter_name': 'formatter_pricesize',
                    'df_column': 'text',
                }
            }, {
                'name': 'plotly_df_to_data',
            }],
        },
        'best back.hold_delay': {
            'chart_args': {
                'visible': 'legendonly',
            },
        },
        'best lay.hold_delay': {
            'chart_args': {
                'visible': 'legendonly',
            },
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
        'tv': {
            'chart': 'Bar',
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
    }


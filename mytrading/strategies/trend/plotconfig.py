def get_trend_plot_configs(tv_bar_width_ms, tv_opacity):
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
            'chart_args': {
                'visible': 'legendonly',
            },
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
            },  {
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

        'ltp': {
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
            }, {
                'name': 'plotly_df_to_data',
            }],
            'chart_args': {
                'mode': 'lines+markers',
                'visible': 'legendonly',
            },
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
                'opacity': tv_opacity,
                'width': tv_bar_width_ms,  # 1 seconds width of bars
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
                    'n_seconds': int(tv_bar_width_ms/1000),
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

        'ltp smoothed': {
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'ltp smoothed.regression',
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_formatter',
                'kwargs': {
                    'formatter_name': 'formatter_regression',
                    'df_column': 'text',
                }
            }, {
                'name': 'plotly_df_to_data',
            }],
        },

        'best lay smoothed': {
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'best lay smoothed.regression',
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_formatter',
                'kwargs': {
                    'formatter_name': 'formatter_regression',
                    'df_column': 'text',
                }
            }, {
                'name': 'plotly_df_to_data',
            }],
        },

        'best back smoothed': {
            'value_processors': [{
                'name': 'plotly_set_attrs',
                'kwargs': {
                    'attr_configs': [{
                        'feature_name': 'best back smoothed.regression',
                        'attr_names': ['text'],
                    }],
                }
            }, {
                'name': 'plotly_df_formatter',
                'kwargs': {
                    'formatter_name': 'formatter_regression',
                    'df_column': 'text',
                }
            },{
                'name': 'plotly_df_to_data',
            }],
        },

        'ltp smoothed.regression': {
            'ignore': True,
        },

        'best back smoothed.regression': {
            'ignore': True,
        },

        'best lay smoothed.regression': {
            'ignore': True,
        },

    }
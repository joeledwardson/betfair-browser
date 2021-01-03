from typing import List, Dict


def ladder_value_processors(ladder_feature) -> List[Dict]:
    return [{
        'name': 'plotly_set_attrs',
        'kwargs': {
            'attr_configs': [{
                'feature_name': ladder_feature,
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
    }]


def ltp_value_processors(tv_feature, spread_feature) -> List[Dict]:
    return [{
        'name': 'plotly_set_attrs',
        'kwargs': {
            'attr_configs': [{
                'feature_name': tv_feature,
                'attr_names': ['tv_text'],
            }, {
                'feature_name': spread_feature,
                'attr_names': ['spread_text'],
            }],
        }
    }, {
        'name': 'plotly_df_fillna',
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_generic',
            'df_column': 'spread_text',
            'formatter_kwargs': {
                'name': 'spread',
            }
        }
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_decimal',
            'df_column': 'tv_text',
            'formatter_kwargs': {
                'name': 'traded vol',
                'prefix': '£',
            }
        }
    }, {
        'name': 'plotly_df_text_join',
        'kwargs': {
            'dest_col': 'text',
            'source_cols': [
                'tv_text',
                'spread_text',
            ],
        }
    }, {
        'name': 'plotly_df_to_data',
    }]


def smooth_chart_kwargs(color_0, color_1) -> Dict:
    return {
        'mode': 'lines+markers',
        'line_color': 'black',
        'marker': {
            'colorscale': [
                [0, color_0],
                [1, color_1]
            ],
            'cmid': 0,
        }
    }


def smooth_value_processors(ticks_feature_name, max_diff_feature) -> List[Dict]:
    return [{
        'name': 'plotly_set_attrs',
        'kwargs': {
            'attr_configs': [{
                'feature_name': ticks_feature_name + '.regression',
                'attr_names': ['text_regression', 'marker_color'],
            }, {
                'feature_name': ticks_feature_name,
                'attr_names': ['text_ticks'],
            }, {
                'feature_name': ticks_feature_name + '.comparison',
                'attr_names': ['text_tick_comparison'],
            }, {
                'feature_name': max_diff_feature,
                'attr_names': ['text_max_diff']
            }],
        },
    },  {
        'name': 'plotly_df_fillna',
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_regression',
            'df_column': 'text_regression',
        }
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_generic',
            'df_column': 'text_ticks',
            'formatter_kwargs': {
                'name': 'tick index',
            }
        }
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_generic',
            'df_column': 'text_tick_comparison',
            'formatter_kwargs': {
                'name': 'tick difference',
            }
        }
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_generic',
            'df_column': 'text_max_diff',
            'formatter_kwargs': {
                'name': 'max tick difference',
            }
        }
    }, {
        'name': 'plotly_df_text_join',
        'kwargs': {
            'dest_col': 'text',
            'source_cols': [
                'text_regression',
                'text_ticks',
                'text_tick_comparison',
                'text_max_diff'
            ],
        }
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_regression_color',
            'df_column': 'marker_color',
        }
    }, {
        'name': 'plotly_df_to_data',
    }]


def bar_chart_kwargs(color_0, color_1, opacity, width_ms):
    return {
        'marker': {
            'colorscale': [
                [0, color_0],
                [1, color_1]
            ],
            'cmid': 0,  # with grey 0 scale
        },
        'opacity': opacity,
        'width': width_ms,  # 1 seconds width of bars
        'offset': 0,  # end of bar to be aligned with timestamp
    }


def tv_bar_value_processors(tv_name, tv_bar_width_ms):
    return [{
        'name': 'plotly_set_attrs',
        'kwargs': {
            'attr_configs': [{
                'feature_name': tv_name,
                'attr_names': ['text', 'marker_color'],
                'feature_value_processors': [{
                    'name': 'plotly_data_to_series'
                }, {
                    'name': 'plotly_df_diff'
                }, {
                    'name': 'plotly_series_to_data'
                }],
            }],
        },
        }, {
            'name': 'plotly_values_resampler',
            'kwargs': {
                'n_seconds': int(tv_bar_width_ms/1000),
                'agg_function': {
                    'y': 'sum',
                    'text': 'sum',
                    'marker_color': 'sum',
                }
            }
        }, {
            'name': 'plotly_df_formatter',
            'kwargs': {
                'formatter_name': 'formatter_decimal',
                'df_column': 'text',
                'formatter_kwargs': {
                    'name': tv_name,
                    'prefix': '£',
                }
            },
        },{
            'name': 'plotly_df_to_data'
        }
    ]


IGNORE_LIST = [
    'back ladder',
    'lay ladder',
    'wom',
    'spread',
    'tv',
    'ltp max diff',
    'best back max diff',
    'best lay max diff',
    'ltp smoothed ticks',
    'ltp smoothed ticks.regression',
    'ltp smoothed ticks.comparison',
    'best back smoothed ticks',
    'best back smoothed ticks.regression',
    'best back smoothed ticks.comparison',
    'best lay smoothed ticks',
    'best lay smoothed ticks.regression',
    'best lay smoothed ticks.comparison',
]


def get_trend_plot_configs(tv_bar_width_ms, tv_opacity):

    return {

        'best back': {
            'chart_args': {
                'visible': 'legendonly',
            },
            'value_processors': ladder_value_processors('back ladder'),
        },

        'best lay': {
            'chart_args': {
                'visible': 'legendonly',
            },
            'value_processors': ladder_value_processors('lay ladder'),
        },

        'ltp': {
            'value_processors': ltp_value_processors(
                tv_feature='tv',
                spread_feature='spread'
            ),
            'chart_args': {
                'mode': 'lines+markers',
                'visible': 'legendonly',
            },
        },

        'book split': {
            'chart': 'Bar',
            # default plotly colours go white, so use a green to red scale
            'chart_args': bar_chart_kwargs('rgb(250,50,50)', 'rgb(50,250,50)', tv_opacity, tv_bar_width_ms),
            'trace_args': {
                'secondary_y': True
            },
            'value_processors':tv_bar_value_processors('tv', tv_bar_width_ms),
        },

        'ltp smoothed': {
            # yellow to blue scale
            'chart_args': smooth_chart_kwargs(
                color_0='rgb(255,255,0)',
                color_1='rgb(0,0,255)',
            ),
            'value_processors': smooth_value_processors(
                ticks_feature_name='ltp smoothed ticks',
                max_diff_feature='ltp max diff',
            ),
        },

        'best back smoothed': {
            # use red to green scale
            'chart_args': smooth_chart_kwargs(
                color_0='rgb(255,0,0)',
                color_1='rgb(0,255,0)',
            ),
            'value_processors': smooth_value_processors(
                ticks_feature_name='best back smoothed ticks',
                max_diff_feature='best back max diff',
            )
        },

        'best lay smoothed': {
            # use red to green scale
            'chart_args': smooth_chart_kwargs(
                color_0='rgb(255,0,0)',
                color_1='rgb(0,255,0)',
            ),
            'value_processors': smooth_value_processors(
                ticks_feature_name='best lay smoothed ticks',
                max_diff_feature='best lay max diff',
            )
        },

        **{f: {'ignore': True} for f in IGNORE_LIST},
    }
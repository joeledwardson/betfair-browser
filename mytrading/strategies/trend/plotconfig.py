from typing import List, Dict
from ...visual import FigConfigUtils as CfgUtl




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


def smooth_value_processors(ftr_tks, ftr_cmp, ftr_dif) -> List[Dict]:
    return [{
        'name': 'plotly_set_attrs',
        'kwargs': {
            'attr_configs': [{
                'feature_name': ftr_tks,
                'attr_names': ['text_ticks'],
            }, {
                'feature_name': ftr_cmp,
                'attr_names': ['text_tick_comparison', 'marker_color'],
            }, {
                'feature_name': ftr_dif,
                'attr_names': ['text_max_diff']
            }],
        },
    },  {
        'name': 'plotly_df_fillna',
    },
    # {
    #     'name': 'plotly_df_formatter',
    #     'kwargs': {
    #         'formatter_name': 'formatter_regression',
    #         'df_column': 'text_regression',
    #     }
    # },
    {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_decimal',
            'df_column': 'text_ticks',
            'formatter_kwargs': {
                'name': 'tick index',
                'n_decimals': 1,
            }
        }
    }, {
        'name': 'plotly_df_formatter',
        'kwargs': {
            'formatter_name': 'formatter_decimal',
            'df_column': 'text_tick_comparison',
            'formatter_kwargs': {
                'name': 'tick difference',
                'n_decimals': 2,
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
                # 'text_regression',
                'text_ticks',
                'text_tick_comparison',
                'text_max_diff'
            ],
        }
    },
    # {
    #     'name': 'plotly_df_formatter',
    #     'kwargs': {
    #         'formatter_name': 'formatter_regression_color',
    #         'df_column': 'marker_color',
    #     }
    # },
    {
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


#
# def ltp_value_procs():
#     return [
#         {
#             'name': 'plotly_data_to_series'
#         },
#         {
#             'name': 'plotly_values_resampler',
#             'kwargs': {
#                 'n_seconds': 1,
#                 'agg_function': 'mean',
#             }
#         }, {
#             'name': 'plotly_df_fillna'
#         }, {
#             'name': 'plotly_values_rolling',
#             'kwargs': {
#                 'n_seconds': 3,
#                 'agg_function': 'mean',
#             },
#         }, {
#             'name': 'plotly_series_to_data'
#         }
#     ]




class PlotConfig:
    IGNORE_LIST = [
        'bcklad',
        'laylad',
        'wom',
        'spread',
        'tv',
        'ltp.t',
        'bck.t',
        'lay.t',
        'ltp.t.mdf',
        'bck.t.mdf',
        'lay.t.mdf',
        'ltp.t.sm',
        'bck.t.sm',
        'lay.t.sm',
        'ltp.t.sm.cmp',
        'bck.t.sm.cmp',
        'lay.t.sm.cmp',
    ]

    def __init__(self, bar_width_ms, tv_opacity):
        self._bar_width_ms = bar_width_ms
        self._tv_opacity = tv_opacity

    @staticmethod
    def prcs_ltp(ltp, tv, spread, split) -> List[Dict]:
        return [{
            'name': 'prc_ftrstodf',
            'kwargs': {
                'ftr_keys': {
                    'y': ltp,
                    'tv_text': tv,
                    'spread_text': spread,
                    'split_text': split,
                }
            }
        }, {
            'name': 'prc_dffillna',
        }, {
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'spread_text',
                'fmt_spec': 'Spread: {0}'
            }
        }, {
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'tv_text',
                'fmt_spec': 'Traded Volume: £{0:.2f}'
            }
        }, {
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'split_text',
                'fmt_spec': 'Book split: £{0:.2f}'
            }
        }, {
            'name': 'prc_dftxtjoin',
            'kwargs': {
                'dest_col': 'text',
                'src_cols': [
                    'tv_text',
                    'spread_text',
                    'split_text',
                ],
            }
        }, {
            'name': 'prc_dfdrop',
            'kwargs': {
                'cols': [
                    'tv_text',
                    'spread_text',
                    'split_text'
                ]
            }
        }, {
            'name': 'prc_dftodict',
        }]

    @staticmethod
    def prcs_tvbar(tv, bar_width_ms):
        return [{
            'name': 'prc_getftr',
            'keys': {
                'key_out': 'key_tv'
            },
            'kwargs': {
                'ftr_key': tv
            }
        }, {
            'name': 'prc_dfdiff',
            'keys': {
                'key_in': 'key_tv',
                'key_out': 'key_tv'
            }
        }, {
            'name': 'prc_buftodf',
            'kwargs': {
                'buf_cfg': {
                    'y': 'key_0',
                    'text': 'key_tv'
                }
            }
        }, {
            'name': 'prc_resmp',
            'kwargs': {
                'n_seconds': int(bar_width_ms / 1000),
                'agg_function': {
                    'y': 'sum',
                    'text': 'sum'
                }
            }
        }, {
            'name': 'prc_dfcp',
            'kwargs': {
                'col_src': 'text',
                'col_out': 'marker_color'
            }
        }, {
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'text',
                'fmt_spec': 'Traded volume: £{0:.2f}'
            }
        }, {
            'name': 'prc_dftodict'
        }]

    @property
    def configs(self):
        return {
            f: {
                'ignore': True
            } for f in self.IGNORE_LIST
        } | {

            'bck': {
                'chart_args': {
                    'visible': 'legendonly',
                },
                'value_processors': CfgUtl.lad_prcs('bck', 'bcklad'),
            },

            'lay': {
                'chart_args': {
                    'visible': 'legendonly',
                },
                'value_processors': CfgUtl.lad_prcs('lay', 'laylad'),
            },

            'ltp': {
                'value_processors': self.prcs_ltp(
                    ltp='ltp',
                    tv='tv',
                    spread='spread',
                    split='split.sum',
                ),
                'chart_args': {
                    'mode': 'lines+markers',
                    'visible': 'legendonly',
                },
            },

            'split': {
                'chart': 'Bar',
                'chart_args': {
                    'marker': { # default plotly colours go white, so use a green to red scale
                        'colorscale': [
                            [0, 'rgb(250,50,50)'],
                            [1, 'rgb(50,250,50)']
                        ],
                        'cmid': 0,  # with grey 0 scale
                    },
                    'opacity': self._tv_opacity,
                    'width': self._bar_width_ms,  # 1 seconds width of bars
                    'offset': 0,  # end of bar to be aligned with timestamp
                },
                'trace_args': {
                    'secondary_y': True
                },
                'value_processors': self.prcs_tvbar('tv', self._bar_width_ms),
            },

            'split.sum': {
                'chart_args': {
                    'visible': 'legendonly',
                },
                'trace_args': {
                    'secondary_y': True
                },
            },

            'split.tot': {
                'chart_args': {
                    'texttemplate': "%{label}: £%{value:.2f}",
                },
                'trace_args': {
                    'secondary_y': True
                },
            },

            'ltp.sm': {
                # yellow to blue scale
                'chart_args': smooth_chart_kwargs(
                    color_0='rgb(255,255,0)',
                    color_1='rgb(0,0,255)',
                ),
                'value_processors': [{
                    'name': 'plotly_set_attrs',
                    'kwargs': {
                        'attr_configs': [{
                            'feature_name': 'split.sum',
                            'attr_names': ['text', 'marker_color'],
                        }],
                    },
                }, {
                    'name': 'plotly_df_formatter',
                    'kwargs': {
                        'formatter_name': 'formatter_decimal',
                        'df_column': 'text',
                        'formatter_kwargs': {
                            'name': 'book split',
                            'n_decimals': 2,
                        }
                    },
                }, {
                    'name': 'plotly_df_to_data',
                }],
            },

            'bck.sm': {
                # use red to green scale
                'chart_args': smooth_chart_kwargs(
                    color_0='rgb(255,0,0)',
                    color_1='rgb(0,255,0)',
                ),
                'value_processors': smooth_value_processors(
                    ftr_tks='bck.t.sm',
                    ftr_cmp='bck.t.sm.cmp',
                    ftr_dif='bck.t.mdf',
                )
            },

            'lay.sm': {
                # use red to green scale
                'chart_args': smooth_chart_kwargs(
                    color_0='rgb(255,0,0)',
                    color_1='rgb(0,255,0)',
                ),
                'value_processors': smooth_value_processors(
                    ftr_tks='lay.t.sm',
                    ftr_cmp='lay.t.sm.cmp',
                    ftr_dif='lay.t.mdf',
                )
            },

            # 'ltp.min': {
            #     'value_processors': ltp_value_procs(),
            # },
            #
            # 'ltp.max': {
            #     'value_processors': ltp_value_procs(),
            # },

        }
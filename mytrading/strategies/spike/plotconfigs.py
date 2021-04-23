from typing import Dict


class PlotConfig:
    IGNORE = [
        'back ladder',
        'lay ladder',
        'spread',
        'spread.smp',
        'spread.smp.avg',
        'wom',
        'tvlad',
        'tvlad.dif',
        'tvlad.dif.max',
        'tvlad.dif.max.smp',
        'tvlad.dif',
        'tvlad.dif.min',
        'tvlad.dif.min.smp',
    ]

    def __init__(self, ltp_diff_opacity, ltp_diff_s):
        self._ltp_diff_opacity = ltp_diff_opacity
        self._ltp_diff_s = ltp_diff_s

    def _lad_procs(self, ftr_key, lad_key):
        """return processors to add ladder feature of price sizes to back/lay feature"""
        return [
            {
                'name': 'prc_ftrstodf',
                'kwargs': {
                    'ftr_keys': {
                        'y': ftr_key,
                        'text': lad_key
                    }
                }
            }, {
                'name': 'prc_dffmtps',
                'kwargs': {
                    'df_col': 'text'
                }
            }, {
                'name': 'prc_dftodict'
            }
        ]

    @property
    def configs(self):
        return {
            k: {
                'ignore': True
            } for k in self.IGNORE
        } | {
            'tvlad.dif.min.smp.avg': {
                'chart_args': {
                    'mode': 'lines+markers'
                }
            },
            'best back': {
                'value_processors': self._lad_procs('best back', 'back ladder'),
            },
            'best lay': {
                'value_processors': self._lad_procs('best lay', 'lay ladder')
            },
            'ltp': {
                'chart_args': {
                    'mode': 'lines+markers'
                },
                'value_processors': [{
                    'name': 'prc_ftrstodf',
                    'kwargs': {
                        'ftr_keys': {
                            'y': 'ltp',
                            'text':'tv',
                        }
                    }
                }, {
                    'name': 'prc_dffillna'
                }, {
                    'name': 'prc_dffmtstr',
                    'kwargs': {
                        'df_col': 'text',
                        'fmt_spec': 'Traded Volume: £{0:.2f}'
                    }
                }, {
                    'name': 'prc_dftodict',
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
                    'opacity': self._ltp_diff_opacity,
                    'width': 1000,  # 1 seconds width of bars
                    'offset': 0,  # end of bar to be aligned with timestamp
                },
                'trace_args': {
                    'secondary_y': True
                },
                'value_processors': [{
                    'name': 'prc_datatodf',
                    'kwargs': {
                        'data_col': 'y'
                    }
                }, {
                    'name': 'prc_dfdiff'
                }, {
                    'name': 'prc_ftrtodf',
                    'keys': {
                        'key_out': 'key_1'
                    },
                    'kwargs': {
                        'ftr_key': 'wom',
                        'data_col': 'text'
                    }
                }, {
                    'name': 'prc_dfconcat',
                    'kwargs': {
                        'buf_keys': ['key_0', 'key_1'],
                        'concat_kwargs': {
                            'axis': 1
                        }
                    }
                }, {
                    'name': 'prc_dftypes',
                    'kwargs': {
                        'dtypes': {
                            'y': 'float',
                            'text': 'float',
                        }
                    }
                }, {
                    'name': 'prc_resmp',
                    'kwargs': {
                        'n_seconds': self._ltp_diff_s,
                        'agg_function': {
                            'y': 'sum',
                            'text': 'mean',
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
                        'fmt_spec': 'Weight of Money: £{0:.2f}'
                    },
                }, {
                    'name': 'prc_dftodict'
                }],
            },
        }



def get_spike_plot_configsmk2(ltp_diff_opacity, ltp_diff_s) -> Dict:
    return {
        'tvlad.dif.min.s': {
            'chart_args': {
                'mode': 'lines+markers'
            }
        },
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
        'tvlad': {
            'ignore': True,
        },
        'tvlad.dif': {
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
                'name': 'data_nptype',
                'kwargs': {
                    'data_types': {
                        'y': 'float',
                        'text': 'float',
                        'marker_color': 'float'
                    }
                }
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


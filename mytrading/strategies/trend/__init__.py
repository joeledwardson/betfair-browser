from typing import Dict, List
from ...strategy.feature import FeatureCfgUtils as FtrUtil
from ...visual import FigConfigUtils as PltUtil


class FeatureConfig:
    @staticmethod
    def side_kwargs(diff_s, ladder_sampling_ms, ladder_sampling_count) -> Dict:
        return {
            'cache_secs': diff_s,
            'cache_insidewindow': False,
            'sub_features_config': {
                FtrUtil.KEY_TICKS: {
                    'name': 'RFTick',
                    'kwargs': {
                        'cache_secs': diff_s,
                        'cache_insidewindow': False,
                        'sub_features_config': {
                            FtrUtil.KEY_MAX_DIF: {
                                'name': 'RFMaxDif'
                            },
                            FtrUtil.KEY_SAMPLE: {
                                'name': 'RFSample',
                                'kwargs': {
                                    'periodic_ms': ladder_sampling_ms,
                                    'cache_count': ladder_sampling_count,
                                    'sub_features_config': {
                                        FtrUtil.KEY_AVERAGE: {
                                            'name': 'RFMvAvg',
                                            'kwargs': {
                                                'cache_secs': diff_s,
                                                'sub_features_config': {
                                                    FtrUtil.KEY_COMPARE: {
                                                        'name': 'RFDif'
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                FtrUtil.KEY_SAMPLE: {
                    'name': 'RFSample',
                    'kwargs': {
                        'periodic_ms': ladder_sampling_ms,
                        'cache_count': ladder_sampling_count,
                        'sub_features_config': {
                            FtrUtil.KEY_AVERAGE: {
                                'name': 'RFMvAvg'
                            }
                        }
                    }
                }
            }
        }

    def __init__(
        self,
        spread_sampling_ms,
        spread_sampling_count,
        wom_ticks,
        ltp_window_width_s,
        ltp_window_sampling_ms,
        ltp_window_sampling_count,
        ladder_sampling_ms,
        ladder_sampling_count,
        ltp_sampling_ms,
        ltp_sampling_count,
        n_ladder_elements,
        diff_s,
        split_sum_s,
    ):
        self._config = {
            'spread': {
                'name': 'RFLadSprd',
                'kwargs': {
                    'sub_features_config': FtrUtil.sample_smooth(
                        spread_sampling_ms,
                        spread_sampling_count
                    )
                }
            },

            'lay': {
                'name': 'RFLay',
                'kwargs': self.side_kwargs(diff_s, ladder_sampling_ms, ladder_sampling_count)
            },

            'bck': {
                'name': 'RFBck',
                'kwargs': self.side_kwargs(diff_s, ladder_sampling_ms, ladder_sampling_count)
            },

            'ltp': {
                'name': 'RFLTP',
                'kwargs': {
                    'sub_features_config': FtrUtil.sample_smooth(
                        ltp_sampling_ms,
                        ltp_sampling_count
                    ),
                }
            },

            'tvlad': {
                'name': 'RFTVLad',
                'kwargs': FtrUtil.tvlad_kwargs(
                    ltp_window_width_s,
                    ltp_window_sampling_ms,
                    ltp_window_sampling_count
                )
            },

            'bcklad': {
                'name': 'RFLadBck',
                'kwargs': {
                    'n_elements': n_ladder_elements,
                }
            },

            'laylad': {
                'name': 'RFLadLay',
                'kwargs': {
                    'n_elements': n_ladder_elements,
                }
            },

            'wom': {
                'name': 'RFWOM',
                'kwargs': {
                    'wom_ticks': wom_ticks
                },
            },

            'split': {
                'name': 'RFBkSplit',
                'kwargs': {
                    'cache_secs': split_sum_s,
                    'cache_insidewindow': False,
                    'sub_features_config': {
                        'sum': {
                            'name': 'RFSum'
                        },
                        'tot': {
                            'name': 'RFIncSum'
                        }
                    }
                }
            },
            'tv': {
                'name': 'RFTVTot',
            },
        }

    @property
    def configs(self):
        return self._config


class PlotConfig:
    IGNORE_LIST = [
        'bcklad',
        'laylad',
        'wom',
        'spread',
        'spread.smp',
        'spread.smp.avg',
        'tv',
        'bck.smp',
        'lay.smp',
        'bck.tck',
        'lay.tck',
        'bck.tck.mdf',
        'lay.tck.mdf',
        'bck.tck.smp',
        'lay.tck.smp',
        'bck.tck.smp.avg',
        'lay.tck.smp.avg',
        'bck.tck.smp.avg.cmp',
        'lay.tck.smp.avg.cmp',
        'ltp.smp',
        'tvlad',
        'tvlad.dif',
        'tvlad.dif.max',
        'tvlad.dif.max.smp',
        'tvlad.dif',
        'tvlad.dif.min',
        'tvlad.dif.min.smp',
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

    @staticmethod
    def smooth_value_processors(ftr_src, ftr_tks, ftr_cmp, ftr_dif) -> List[Dict]:
        return [{
            'name': 'prc_ftrstodf',
            'kwargs': {
                'ftr_keys': {
                    'y': ftr_src,
                    'marker_color': ftr_cmp,
                    'text_ticks': ftr_tks,
                    'text_tick_comp': ftr_cmp,
                    'text_max_diff': ftr_dif
                }
            },
        }, {
            'name': 'prc_dffillna',
        }, {
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'text_ticks',
                'fmt_spec': 'Tick: {0:.2f}'
            }
        }, {
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'text_tick_comp',
                'fmt_spec': 'Tick difference: {0:.2f}'
            }
        }, {
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'text_max_diff',
                'fmt_spec': 'Max tick difference: {0:.2f}',
            }
        }, {
            'name': 'prc_dftxtjoin',
            'kwargs': {
                'dest_col': 'text',
                'src_cols': [
                    'text_ticks',
                    'text_tick_comp',
                    'text_max_diff'
                ],
            }
        }, {
            'name': 'prc_dfdrop',
            'kwargs': {
                'cols': [
                    'text_ticks',
                    'text_tick_comp',
                    'text_max_diff'
                ]
            }
        }, {
            'name': 'prc_dftodict',
        }]

    @property
    def configs(self):
        return {
            f: {
                'ignore': True
            } for f in self.IGNORE_LIST
        } | {

            'tvlad.dif.max.smp.avg': {
                'rename': 'ltp max'
            },

            'tvlad.dif.min.smp.avg': {
                'rename': 'ltp min'
            },

            'bck': {
                'chart_args': {
                    'visible': 'legendonly',
                },
                'value_processors': PltUtil.lad_prcs('bck', 'bcklad'),
            },

            'lay': {
                'chart_args': {
                    'visible': 'legendonly',
                },
                'value_processors': PltUtil.lad_prcs('lay', 'laylad'),
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
                # 'trace_args': {
                #     'secondary_y': True
                # },
                'ignore': True
            },

            'ltp.smp.avg': {
                'chart_args': PltUtil.chart_colorscale(
                    color_0='rgb(255,255,0)',
                    color_1='rgb(0,0,255)'  # yellow to blue scale
                ),
                'value_processors': [{
                    'name': 'prc_ftrstodf',
                    'kwargs': {
                        'ftr_keys': {
                            'y': 'ltp.smp.avg',
                            'text': 'split.sum',
                        },
                    },
                }, {
                   'name': 'prc_dffillna'
                }, {
                    'name':  'prc_dfcp',
                    'kwargs': {
                        'col_src': 'text',
                        'col_out': 'marker_color'
                    }
                }, {
                    'name': 'prc_dffmtstr',
                    'kwargs': {
                        'df_col': 'text',
                        'fmt_spec': 'Book split: £{0:.2f}'
                    }
                }, {
                    'name': 'prc_dftodict',
                }],
                'rename': 'ltp smoothed'
            },

            'bck.smp.avg': {
                # use red to green scale
                'chart_args': PltUtil.chart_colorscale(
                    color_0='rgb(255,0,0)',
                    color_1='rgb(0,255,0)',
                ),
                'value_processors': self.smooth_value_processors(
                    ftr_src='bck.smp.avg',
                    ftr_tks='bck.tck.smp.avg',
                    ftr_cmp='bck.tck.smp.avg.cmp',
                    ftr_dif='bck.tck.mdf',
                ),
                'rename': 'back smoothed'
            },

            'lay.smp.avg': {
                # use red to green scale
                'chart_args': PltUtil.chart_colorscale(
                    color_0='rgb(255,0,0)',
                    color_1='rgb(0,255,0)',
                ),
                'value_processors': self.smooth_value_processors(
                    ftr_src='lay.smp.avg',
                    ftr_tks='lay.tck.smp.avg',
                    ftr_cmp='lay.tck.smp.avg.cmp',
                    ftr_dif='lay.tck.mdf',
                ),
                'rename': 'lay smoothed'
            },
        }

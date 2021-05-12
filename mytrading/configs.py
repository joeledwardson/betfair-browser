from typing import List, Dict, Optional
from myutils.myregistrar import MyRegistrar
from myutils import mydict
import os, yaml
from os import path
from .exceptions import FeatureConfigException


reg_plots = MyRegistrar()
reg_features = MyRegistrar()

KEY_SAMPLE = 'smp'
KEY_AVERAGE = 'avg'
KEY_TICKS = 'tck'
KEY_MAX_DIF = 'mdf'
KEY_COMPARE = 'cmp'


class ConfigGenerator:
    CONFIG_SPEC = {
        'name': {
            'type': str
        },
        'kwargs': {
            'type': dict
        }
    }

    def __init__(self, cfg_dir: str, out_dir, reg: MyRegistrar):
        self._cfg_dir = path.abspath(path.expandvars(cfg_dir))
        if not path.isdir(self._cfg_dir):
            raise FeatureConfigException(f'configuration dir "{self._cfg_dir}" is not a directory')
        self._out_dir = path.abspath(path.expandvars(out_dir))
        if not path.isdir(self._out_dir):
            raise FeatureConfigException(f'output dir "{self._out_dir}" is not a directory')
        self._reg = reg

    def reload(self):
        _, _, filenames = next(os.walk(self._cfg_dir))
        for fn in filenames:
            p_in = path.join(self._cfg_dir, fn)
            with open(p_in, 'r') as f:
                data = f.read()
            file_cfg = yaml.load(data, yaml.FullLoader)
            mydict.validate_config(file_cfg, self.CONFIG_SPEC)
            reg_nm = file_cfg['name']
            reg_kwargs = file_cfg['kwargs']
            ftr_cfg = self._reg[reg_nm](**reg_kwargs)
            p_out = path.join(self._out_dir, fn)
            with open(p_out, 'w') as f:
                f.write(yaml.dump(ftr_cfg))


def _plot_procs_lad(ftr_key, lad_key):
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


def _plot_colorscale(color_0, color_1) -> Dict:
    """`chart_args` argument to set colorscale with lines+markers"""
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


def _ftr_smooth(sample_ms, cache_count):
    """sub-features config for sampling and then moving average"""
    return {
        KEY_SAMPLE:  {
            'name': 'RFSample',
            'kwargs': {
                'periodic_ms': sample_ms,
                'cache_count': cache_count,
                'sub_features_config': {
                    KEY_AVERAGE: {
                        'name': 'RFMvAvg'
                    }
                }
            }
        }
    }


def _ftr_tick(sub_features_config=None):
    """sub-feature converting parent to tick"""
    return {
        'name': 'RunnerFeatureSub',
        'kwargs': {
            'value_processors_config': [{
                'name': 'value_processor_to_tick',
            }],
            'sub_features_config': sub_features_config,
        },
    }


def _ftr_tvlad(window_s, sampling_ms, cache_count):
    """traded volume `TVLad` feature sub-config for creating max/min values over window, sampling then moving avg"""
    return {
        'cache_secs': window_s,
        'cache_insidewindow': False,
        'sub_features_config': {
            'dif': {
                'name': 'RFTVLadDif',
                'kwargs': {
                    'sub_features_config': {
                        'max': {
                            'name': 'RFTVLadMax',
                            'kwargs': {
                                'sub_features_config': _ftr_smooth(sampling_ms, cache_count)
                            }
                        },
                        'min': {
                            'name': 'RFTVLadMin',
                            'kwargs': {
                                'sub_features_config': _ftr_smooth(sampling_ms, cache_count)
                            }
                        }
                    }
                }
            }
        }
    }


@reg_features.register_element
def feature_configs_spike(
        n_ladder_elements,
        n_wom_ticks,
        ltp_window_width_s,
        ltp_window_sampling_ms,
        ltp_window_sampling_count,
        spread_sampling_ms,
        spread_sampling_count,
) -> Dict[str, Dict]:
    """
    Get a dict of default runner features, where each entry is a dictionary of:
    - key: feature usage name
    - value: dict of
        - 'name': class name of feature
        - 'kwargs': dict of constructor arguments used when creating feature
    """

    def ltp_win_kwargs(sample_ms, cache_count):
        d = {
            'sub_features_config': {
                'smp': {
                    'name': 'RFSample',
                    'kwargs': {
                        'periodic_ms': sample_ms,
                        'cache_count': cache_count,
                        'sub_features_config': {
                            'avg': {
                                'name': 'RFMvAvg'
                            }
                        }
                    }
                }
            }
        }
        return d

    return {

        'best back': {
            'name': 'RFBck',
        },

        'best lay': {
            'name': 'RFLay',
        },

        'back ladder': {
            'name': 'RFLadBck',
            'kwargs': {
                'n_elements': n_ladder_elements,
            }
        },

        'lay ladder': {
            'name': 'RFLadLay',
            'kwargs': {
                'n_elements': n_ladder_elements,
            }
        },

        'wom': {
            'name': 'RFWOM',
            'kwargs': {
                'wom_ticks': n_wom_ticks
            },
        },

        'tvlad': {
            'name': 'RFTVLad',
            'kwargs': {
                'cache_secs': ltp_window_width_s,
                'cache_insidewindow': False,
                'sub_features_config': {
                    'dif': {
                        'name': 'RFTVLadDif',
                        'kwargs': {
                            'sub_features_config': {
                                'max': {
                                    'name': 'RFTVLadMax',
                                    'kwargs': ltp_win_kwargs(ltp_window_sampling_ms, ltp_window_sampling_count)
                                },
                                'min': {
                                    'name': 'RFTVLadMin',
                                    'kwargs': ltp_win_kwargs(ltp_window_sampling_ms, ltp_window_sampling_count)
                                }
                            }
                        }
                    }
                }
            }
        },

        'ltp': {
            'name': 'RFLTP',
        },

        'tv': {
            'name': 'RFTVTot',
        },

        'spread': {
            'name': 'RFLadSprd',
            'kwargs': {
                'sub_features_config': {
                    'smp': {
                        'name': 'RFSample',
                        'kwargs': {
                            'periodic_ms': spread_sampling_ms,
                            'cache_count': spread_sampling_count,
                            'sub_features_config': {
                                'avg': {
                                    'name': 'RFMvAvg'
                                }
                            }
                        }
                    }
                }
            }
        }
    }


@reg_plots.register_element
def plot_configs_spike(
        ltp_diff_opacity,
        ltp_diff_s
):
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

    return {
        k: {
            'ignore': True
        } for k in IGNORE
    } | {
        'best back': {
            'value_processors': _plot_procs_lad('best back', 'back ladder'),
        },
        'best lay': {
            'value_processors': _plot_procs_lad('best lay', 'lay ladder')
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
                        'text': 'tv',
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
                'opacity': ltp_diff_opacity,
                'width': 1000,  # 1 seconds width of bars
                'offset': 0,  # end of bar to be aligned with timestamp
            },
            'trace_args': {
                'secondary_y': True
            },
            'value_processors': [{
                'name': 'prc_dfdiff'
            }, {
                'name': 'prc_getftr',
                'keys': {
                    'key_out': 'key_1'
                },
                'kwargs': {
                    'ftr_key': 'wom',
                }
            }, {
                'name': 'prc_buftodf',
                'kwargs': {
                    'buf_cfg': {
                        'y': 'key_0',
                        'text': 'key_1'
                    },
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
                    'n_seconds': ltp_diff_s,
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
        'tvlad.dif.max.smp.avg': {
            'rename': 'ltp max'
        },
        'tvlad.dif.min.smp.avg': {
            'rename': 'ltp min'
        }
    }


@reg_features.register_element
def feature_configs_smooth(
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
    def side_kwargs(diff_s, ladder_sampling_ms, ladder_sampling_count) -> Dict:
        return {
            'cache_secs': diff_s,
            'cache_insidewindow': False,
            'sub_features_config': {
                KEY_TICKS: {
                    'name': 'RFTick',
                    'kwargs': {
                        'cache_secs': diff_s,
                        'cache_insidewindow': False,
                        'sub_features_config': {
                            KEY_MAX_DIF: {
                                'name': 'RFMaxDif'
                            },
                            KEY_SAMPLE: {
                                'name': 'RFSample',
                                'kwargs': {
                                    'periodic_ms': ladder_sampling_ms,
                                    'cache_count': ladder_sampling_count,
                                    'sub_features_config': {
                                        KEY_AVERAGE: {
                                            'name': 'RFMvAvg',
                                            'kwargs': {
                                                'cache_secs': diff_s,
                                                'sub_features_config': {
                                                    KEY_COMPARE: {
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
                KEY_SAMPLE: {
                    'name': 'RFSample',
                    'kwargs': {
                        'periodic_ms': ladder_sampling_ms,
                        'cache_count': ladder_sampling_count,
                        'sub_features_config': {
                            KEY_AVERAGE: {
                                'name': 'RFMvAvg'
                            }
                        }
                    }
                }
            }
        }

    return {
        'spread': {
            'name': 'RFLadSprd',
            'kwargs': {
                'sub_features_config': _ftr_smooth(
                    spread_sampling_ms,
                    spread_sampling_count
                )
            }
        },

        'lay': {
            'name': 'RFLay',
            'kwargs': side_kwargs(diff_s, ladder_sampling_ms, ladder_sampling_count)
        },

        'bck': {
            'name': 'RFBck',
            'kwargs': side_kwargs(diff_s, ladder_sampling_ms, ladder_sampling_count)
        },

        'ltp': {
            'name': 'RFLTP',
            'kwargs': {
                'sub_features_config': _ftr_smooth(
                    ltp_sampling_ms,
                    ltp_sampling_count
                ),
            }
        },

        'tvlad': {
            'name': 'RFTVLad',
            'kwargs': _ftr_tvlad(
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


@reg_plots.register_element
def plot_configs_smooth(bar_width_ms, tv_opacity):
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

    def prcs_ltp(ltp, tv, spread, split) -> List[Dict]:
        return [{
            'name': 'prc_ftrstodf',
            'kwargs': {
                'ftr_keys': {
                    'y': ltp,
                    'tv_text': tv,
                    'spread_text': spread,
                    'split_text': split,
                    'marker_color': 'wom',
                    'wom_text': 'wom',
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
            'name': 'prc_dffmtstr',
            'kwargs': {
                'df_col': 'wom_text',
                'fmt_spec': 'WOM: £{0:.2f}'
            }
        }, {
            'name': 'prc_dftxtjoin',
            'kwargs': {
                'dest_col': 'text',
                'src_cols': [
                    'tv_text',
                    'spread_text',
                    'split_text',
                    'wom_text'
                ],
            }
        }, {
            'name': 'prc_dfdrop',
            'kwargs': {
                'cols': [
                    'tv_text',
                    'spread_text',
                    'split_text',
                    'wom_text'
                ]
            }
        }, {
            'name': 'prc_dftodict',
        }]

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

    return {
            f: {
                'ignore': True
            } for f in IGNORE_LIST
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
                'value_processors': _plot_procs_lad('bck', 'bcklad'),
            },

            'lay': {
                'chart_args': {
                    'visible': 'legendonly',
                },
                'value_processors': _plot_procs_lad('lay', 'laylad'),
            },

            'ltp': {
                'value_processors': prcs_ltp(
                    ltp='ltp',
                    tv='tv',
                    spread='spread',
                    split='split.sum',
                ),
                'chart_args': {
                    'mode': 'lines+markers',
                    'visible': 'legendonly',
                    'line_color': 'black',
                    'marker': {
                        'colorscale': [
                            [0, 'rgb(255,0,0)'],
                            [1, 'rgb(0,255,0)']
                        ],
                        'cmid': 0,
                    }
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
                    'opacity': tv_opacity,
                    'width': bar_width_ms,  # 1 seconds width of bars
                    'offset': 0,  # end of bar to be aligned with timestamp
                },
                'trace_args': {
                    'secondary_y': True
                },
                'value_processors': prcs_tvbar('tv', bar_width_ms),
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
                'chart_args': _plot_colorscale(
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
                'chart_args': _plot_colorscale(
                    color_0='rgb(255,0,0)',
                    color_1='rgb(0,255,0)',
                ),
                'value_processors': smooth_value_processors(
                    ftr_src='bck.smp.avg',
                    ftr_tks='bck.tck.smp.avg',
                    ftr_cmp='bck.tck.smp.avg.cmp',
                    ftr_dif='bck.tck.mdf',
                ),
                'rename': 'back smoothed'
            },

            'lay.smp.avg': {
                # use red to green scale
                'chart_args': _plot_colorscale(
                    color_0='rgb(255,0,0)',
                    color_1='rgb(0,255,0)',
                ),
                'value_processors': smooth_value_processors(
                    ftr_src='lay.smp.avg',
                    ftr_tks='lay.tck.smp.avg',
                    ftr_cmp='lay.tck.smp.avg.cmp',
                    ftr_dif='lay.tck.mdf',
                ),
                'rename': 'lay smoothed'
            },
        }

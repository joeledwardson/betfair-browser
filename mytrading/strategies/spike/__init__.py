from ...visual import FigConfigUtils as CfgUtl


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

    @property
    def configs(self):
        return {
            k: {
                'ignore': True
            } for k in self.IGNORE
        } | {
            'best back': {
                'value_processors': CfgUtl.lad_procs('best back', 'back ladder'),
            },
            'best lay': {
                'value_processors': CfgUtl.lad_procs('best lay', 'lay ladder')
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
            'tvlad.dif.max.smp.avg': {
                'rename': 'ltp max'
            },
            'tvlad.dif.min.smp.avg': {
                'rename': 'ltp min'
            }
        }
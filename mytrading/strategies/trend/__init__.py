from typing import Dict
from ...strategy.feature.utils import FeatureCfgUtils as CfgUtil


def get_trend_feature_configs(
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
) -> Dict[str, Dict]:
    return {

        'spread': {
            'name': 'RFLadSprd',
            'kwargs': {
                'sub_features_config': CfgUtil.sample_smooth(
                    spread_sampling_ms,
                    spread_sampling_count
                )
            }
        },

        'lay': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': {
                'cache_secs': diff_s,
                'cache_insidewindow': False,
                'sub_features_config': {
                    CfgUtil.KEY_TICKS: {
                        'name': 'RFTick',
                        'kwargs': {
                            'cache_secs': diff_s,
                            'cache_insidewindow': False,
                            'sub_features_config': {
                                CfgUtil.KEY_MAX_DIF: {
                                    'name': 'RFMaxDif'
                                },
                                CfgUtil.KEY_SAMPLE: {
                                    'name': 'RFSample',
                                    'kwargs': {
                                        'periodic_ms': ladder_sampling_ms,
                                        'cache_count': ladder_sampling_count,
                                        'sub_features_config': {
                                            CfgUtil.KEY_AVERAGE: {
                                                'name': 'RFMvAvg',
                                                'kwargs': {
                                                    'cache_secs': diff_s,
                                                    'sub_features_config': {
                                                        CfgUtil.KEY_COMPARE: {
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
                    CfgUtil.KEY_SAMPLE: {
                        'name': 'RFSample',
                        'kwargs': {
                            'periodic_ms': ladder_sampling_ms,
                            'cache_count': ladder_sampling_count,
                            'sub_features_config': {
                                CfgUtil.KEY_AVERAGE: {
                                    'name': 'RFMvAvg'
                                }
                            }
                        }
                    }
                },
            },
        },

        'bck': {
            'name': 'RunnerFeatureBestBack',
            'kwargs': {
                'cache_secs': diff_s,
                'cache_insidewindow': False,
                'sub_features_config': {
                    CfgUtil.KEY_TICKS: {
                        'name': 'RFTick',
                        'kwargs': {
                            'cache_secs': diff_s,
                            'cache_insidewindow': False,
                            'sub_features_config': {
                                CfgUtil.KEY_MAX_DIF: {
                                    'name': 'RFMaxDif'
                                },
                                CfgUtil.KEY_SAMPLE: {
                                    'name': 'RFSample',
                                    'kwargs': {
                                        'periodic_ms': ladder_sampling_ms,
                                        'cache_count': ladder_sampling_count,
                                        'sub_features_config': {
                                            CfgUtil.KEY_AVERAGE: {
                                                'name': 'RFMvAvg',
                                                'kwargs': {
                                                    'cache_secs': diff_s,
                                                    'sub_features_config': {
                                                        CfgUtil.KEY_COMPARE: {
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
                    CfgUtil.KEY_SAMPLE: {
                        'name': 'RFSample',
                        'kwargs': {
                            'periodic_ms': ladder_sampling_ms,
                            'cache_count': ladder_sampling_count,
                            'sub_features_config': {
                                CfgUtil.KEY_AVERAGE: {
                                    'name': 'RFMvAvg'
                                }
                            }
                        }
                    }
                },
            },
        },

        'ltp': {
            'name': 'RunnerFeatureLTP',
            'kwargs': {
                'sub_features_config': CfgUtil.sample_smooth(
                    ltp_sampling_ms,
                    ltp_sampling_count
                ),
            }
        },

        'tvlad': {
            'name': 'RFTVLad',
            'kwargs': CfgUtil.tvlad_kwargs(
                ltp_window_width_s,
                ltp_window_sampling_ms,
                ltp_window_sampling_count
            )
        },

        'bcklad': {
            'name': 'RunnerFeatureBackLadder',
            'kwargs': {
                'n_elements': n_ladder_elements,
            }
        },

        'laylad': {
            'name': 'RunnerFeatureLayLadder',
            'kwargs': {
                'n_elements': n_ladder_elements,
            }
        },

        'wom': {
            'name': 'RunnerFeatureWOM',
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
            'name': 'RunnerFeatureTVTotal',
        },
    }

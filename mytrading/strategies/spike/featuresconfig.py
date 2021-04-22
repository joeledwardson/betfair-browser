from typing import Dict


def ltp_win_kwargs(sample_ms, cache_count):
    d = {
        'sub_features_config': {
            'smp':  {
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


def get_spike_feature_configs(
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
                                    'kwargs': ltp_win_kwargs(ltp_window_sampling_ms, 10)
                                },
                                'min': {
                                    'name': 'RFTVLadMin',
                                    'kwargs': ltp_win_kwargs(ltp_window_sampling_ms, 10)
                                }
                            }
                        }
                    }
                }
            }
        },
        #
        # 'ltp min': {
        #     'name': 'RunnerFeatureTradedWindowMin',
        #     'kwargs': ltp_win_kwargs(ltp_window_sampling_ms, ltp_window_sampling_count, ltp_window_width_s)
        # },
        #
        # 'ltp max': {
        #     'name': 'RunnerFeatureTradedWindowMax',
        #     'kwargs': {
        #         'periodic_ms': ltp_window_sampling_ms,
        #         'periodic_timestamps': True,
        #         'window_s': ltp_window_width_s,
        #         'value_processors_config': [{
        #             'name': 'value_processor_moving_average',
        #             'kwargs': {
        #                 'n_entries': ltp_window_sampling_count
        #             }
        #         }],
        #     }
        # },

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

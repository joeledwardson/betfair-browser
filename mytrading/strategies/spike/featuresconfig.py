from typing import Dict


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
            'name': 'RunnerFeatureBestBack',
        },

        'best lay': {
            'name': 'RunnerFeatureBestLay',
        },

        'back ladder': {
            'name': 'RunnerFeatureBackLadder',
            'kwargs': {
                'n_elements': n_ladder_elements,
            }
        },

        'lay ladder': {
            'name': 'RunnerFeatureLayLadder',
            'kwargs': {
                'n_elements': n_ladder_elements,
            }
        },

        'wom': {
            'name': 'RunnerFeatureWOM',
            'kwargs': {
                'wom_ticks': n_wom_ticks
            },
        },

        'tvlad': {
            'name': 'RFTVLad',
            'kwargs': {
                'cache_secs': 60,
                'cache_insidewindow': True,
                'sub_features_config': {
                    'dif': {
                        'name': 'RFTVLadDif',
                        'kwargs': {
                            'sub_features_config': {
                                'max': {'name': 'RFTVLadMax'},
                                'min': {'name': 'RFTVLadMin'}
                            }
                        }
                    }
                }
            }
        },

        'ltp min': {
            'name': 'RunnerFeatureTradedWindowMin',
            'kwargs': {
                'periodic_ms': ltp_window_sampling_ms,
                'periodic_timestamps': True,
                'window_s': ltp_window_width_s,
                'value_processors_config': [{
                    'name': 'value_processor_moving_average',
                    'kwargs': {
                        'n_entries': ltp_window_sampling_count
                    }
                }],
            }
        },

        'ltp max': {
            'name': 'RunnerFeatureTradedWindowMax',
            'kwargs': {
                'periodic_ms': ltp_window_sampling_ms,
                'periodic_timestamps': True,
                'window_s': ltp_window_width_s,
                'value_processors_config': [{
                    'name': 'value_processor_moving_average',
                    'kwargs': {
                        'n_entries': ltp_window_sampling_count
                    }
                }],
            }
        },

        'ltp': {
            'name': 'RunnerFeatureLTP',
        },

        'tv': {
            'name': 'RunnerFeatureTVTotal',
        },

        'spread': {
            'name': 'RunnerFeatureLadderSpread',
            'kwargs': {
                'periodic_ms': spread_sampling_ms,
                'periodic_timestamps': True,
                'value_processors_config': [{
                    'name': 'value_processor_moving_average',
                    'kwargs': {
                        'n_entries': spread_sampling_count
                    }
                }],
            }
        }

    }

from typing import Dict


# create kwargs for sampling and moving average
def smoothing_kwargs(
        sampling_ms,
        sampling_count,
        regression_count,
):
    return {
        'periodic_ms': sampling_ms,
        'periodic_timestamps': True,
        'value_processor': 'value_processor_moving_average',
        'value_processor_args': {
            'n_entries': sampling_count
        },
        'sub_features_config': {
            'regression': {
                'name': 'RunnerFeatureSubRegression',
                'kwargs': {
                    'element_count': regression_count,
                    'regression_preprocessor': 'value_processor_invert',
                },
            }
        }
    }


def get_trend_feature_configs(
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

        'ltp min': {
            'name': 'RunnerFeatureTradedWindowMin',
            'kwargs': {
                'periodic_ms': ltp_window_sampling_ms,
                'periodic_timestamps': True,
                'window_s': ltp_window_width_s,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': ltp_window_sampling_count
                },
            }
        },

        'ltp max': {
            'name': 'RunnerFeatureTradedWindowMax',
            'kwargs': {
                'periodic_ms': ltp_window_sampling_ms,
                'periodic_timestamps': True,
                'window_s': ltp_window_width_s,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': ltp_window_sampling_count
                },
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
                'period_timestamps': True,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': spread_sampling_count
                },
            }
        }

    }

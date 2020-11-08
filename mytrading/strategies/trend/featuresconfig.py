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
        wom_ticks,
        ltp_window_width_s,
        ltp_window_sampling_ms,
        ltp_window_sampling_count,
        ladder_sampling_ms,
        ladder_sampling_count,
        ladder_regression_count,
        ltp_sampling_ms,
        ltp_sampling_count,
        ltp_regression_count,
        n_ladder_elements,
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
                'wom_ticks': wom_ticks
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

        'best back smoothed': {
            'name': 'RunnerFeatureBestBack',
            'kwargs': smoothing_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
                ladder_regression_count,
            )
        },

        'best lay smoothed': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': smoothing_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
                ladder_regression_count,
            )
        },

        'ltp smoothed': {
            'name': 'RunnerFeatureLTP',
            'kwargs': smoothing_kwargs(
                ltp_sampling_ms,
                ltp_sampling_count,
                ltp_regression_count,
            )
        }

    }

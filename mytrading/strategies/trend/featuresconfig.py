from typing import Dict


# create kwargs for sampling and moving average
def smoothing_kwargs(
        sampling_ms,
        sampling_count,
        regression_count,
        regression_strength_filter,
        regression_gradient_filter
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
                    'regression_gradient_filter': regression_gradient_filter,
                    'regression_strength_filter': regression_strength_filter,
                },
            }
        }
    }


def get_trend_feature_configs(
        wom_ticks,
        ltp_window_s,
        ltp_periodic_ms,
        ltp_moving_average_entries,
        sampling_ms,
        sampling_count,
        regression_count,
        regression_strength_filter,
        regression_gradient_filter,
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
                'periodic_ms': ltp_periodic_ms,
                'periodic_timestamps': True,
                'window_s': ltp_window_s,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': ltp_moving_average_entries
                },
            }
        },

        'ltp max': {
            'name': 'RunnerFeatureTradedWindowMax',
            'kwargs': {
                'periodic_ms': ltp_periodic_ms,
                'periodic_timestamps': True,
                'window_s': ltp_window_s,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': ltp_moving_average_entries
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
                sampling_ms,
                sampling_count,
                regression_count,
                regression_strength_filter,
                regression_gradient_filter
            )
        },

        'best lay smoothed': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': smoothing_kwargs(
                sampling_ms,
                sampling_count,
                regression_count,
                regression_strength_filter,
                regression_gradient_filter
            )
        },

        'ltp smoothed': {
            'name': 'RunnerFeatureLTP',
            'kwargs': smoothing_kwargs(
                sampling_ms,
                sampling_count,
                regression_count,
                regression_strength_filter,
                regression_gradient_filter
            )
        }

    }
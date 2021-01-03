from typing import Dict


def smoothing_kwargs(
        sampling_ms,
        sampling_count,
        regression_count,
        delay_feature_s,
):
    """
    create feature kwargs for sampling and moving average
    and add delayed smoothed values
    """
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
            },
            'ticks': {
                'name': 'RunnerFeatureSub',
                'kwargs': {
                    'value_processor': 'value_processor_to_tick',
                    'sub_features_config': {
                        'comparison': {
                            'name': 'RunnerFeatureSubDelayComparison',
                            'kwargs': {
                                'delay_seconds': delay_feature_s,
                            },
                        },
                    },
                },
            }
        }
    }


def biggest_diff_feature(diff_s, window_var, window_func_key):
    """
    get feature configuration kwargs for a windowed feature with a sub feature computing biggest difference
    """
    return {
        'name': 'RunnerFeatureBiggestDifference',
        'kwargs': {
            'window_s': diff_s,
            'window_function': 'WindowProcessorFeatureBase',
            'window_function_kwargs': {
                'window_var': window_var,
                'window_func_key': window_func_key,
                'feature_processor_key': 'value_processor_to_tick',
            },
            'window_var': window_var,
        }
    }


def get_trend_feature_configs(
        spread_sampling_ms,
        spread_sampling_count,
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
        diff_s,
        delay_feature_s,
) -> Dict[str, Dict]:
    """
    Get a dict of default runner features, where each entry is a dictionary of:
    - key: feature usage name
    - value: dict of
        - 'name': class name of feature
        - 'kwargs': dict of constructor arguments used when creating feature
    """

    return {

        'spread': {
            'name': 'RunnerFeatureLadderSpread',
            'kwargs': {
                'periodic_ms': spread_sampling_ms,
                'periodic_timestamps': True,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': spread_sampling_count
                },
            }
        },

        'best back max diff': biggest_diff_feature(
            diff_s=diff_s,
            window_var='window_backs',
            window_func_key='window_func_best_back',
        ),

        'best lay max diff': biggest_diff_feature(
            diff_s=diff_s,
            window_var='window_lays',
            window_func_key='window_func_best_lay'
        ),

        'ltp max diff': biggest_diff_feature(
            diff_s=diff_s,
            window_var='window_ltps',
            window_func_key='window_func_ltp',
        ),

        'best lay': {
            'name': 'RunnerFeatureBestLay',
        },

        'best back': {
            'name': 'RunnerFeatureBestBack',
        },

        'ltp': {
            'name': 'RunnerFeatureLTP',
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

        'book split': {
            'name': 'RunnerFeatureBookSplitWindow',
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

        'tv': {
            'name': 'RunnerFeatureTVTotal',
        },

        'best back smoothed': {
            'name': 'RunnerFeatureBestBack',
            'kwargs': smoothing_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
                ladder_regression_count,
                delay_feature_s,
            )
        },

        'best lay smoothed': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': smoothing_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
                ladder_regression_count,
                delay_feature_s
            )
        },

        'ltp smoothed': {
            'name': 'RunnerFeatureLTP',
            'kwargs': smoothing_kwargs(
                ltp_sampling_ms,
                ltp_sampling_count,
                ltp_regression_count,
                delay_feature_s,
            )
        }

    }

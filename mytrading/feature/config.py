from typing import Dict


def get_features_default_configs(
        wom_ticks=5,
        ltp_window_s=40,
        ltp_window_delay_s=2,
        ltp_periodic_ms=200,
        ltp_moving_average_entries=10,
        ltp_diff_s=2,
        regression_seconds=2,
        regression_strength_filter=0.1,
        regression_gradient_filter=0.003,
        regression_update_ms=200,
        n_ladder_elements=3,
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
                # 'sub_features_config': {
                #     'delay': {
                #         'name': 'RunnerFeatureSubDelayer',
                #         'kwargs': {
                #             'delay_seconds': ltp_window_delay_s
                #         }
                #     }
                # }
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
                # 'sub_features_config': {
                #     'delay': {
                #         'name': 'RunnerFeatureSubDelayer',
                #         'kwargs': {
                #             'delay_seconds': ltp_window_delay_s
                #         }
                #     }
                # }
            }
        },

        'ltp diff': {
            'name': 'RunnerFeatureTradedDiff',
            'kwargs': {
                'window_s': ltp_diff_s,
            }
        },

        'book split': {
            'name': 'RunnerFeatureBookSplitWindow',
            'kwargs': {
                'window_s': ltp_window_s,
            },
        },

        'ltp': {
            'name': 'RunnerFeatureLTP',
            'kwargs': {
                'sub_features_config': {
                    'previous value': {
                        'name': 'RunnerFeatureSubLastValue'
                    }
                }
            }
        },

        'tv': {
            'name': 'RunnerFeatureTVTotal',
        },

        'best back regression': {
            'name': 'RunnerFeatureRegression',
            'kwargs': {
                'periodic_ms': regression_update_ms,
                'window_function': 'WindowProcessorBestBack',
                'regressions_seconds': regression_seconds,
                'regression_strength_filter': regression_strength_filter,
                'regression_gradient_filter': regression_gradient_filter,
                'regression_preprocessor': 'value_processor_invert',
                'regression_postprocessor': 'value_processor_invert',
            },
        },

        'best lay regression': {
            'name': 'RunnerFeatureRegression',
            'kwargs':  {
                'periodic_ms': regression_update_ms,
                'window_function': 'WindowProcessorBestLay',
                'regressions_seconds': regression_seconds,
                'regression_strength_filter': regression_strength_filter,
                'regression_gradient_filter': regression_gradient_filter * -1,
                'regression_preprocessor': 'value_processor_invert',
                'regression_postprocessor': 'value_processor_invert',
            },
        },
    }
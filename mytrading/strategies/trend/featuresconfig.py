from typing import Dict

KEY_SMOOTH = 'sm'
KEY_TICKS = 't'
KEY_DIFF = 'dif'


def smoothing_kwargs(
        sampling_ms,
        sampling_count,
):
    """
    create feature kwargs for: sample, perform moving average
    """
    return {
        'periodic_ms': sampling_ms,
        'periodic_timestamps': True,
        'value_processors_config': [{
            'name': 'value_processor_moving_average',
            'kwargs': {
                'n_entries': sampling_count
            },
        }]
    }


def smoothing_sub(
        sampling_ms,
        sampling_count,
        subf_config
):
    return {
        KEY_SMOOTH: {
            'name': 'RunnerFeatureSub',
            'kwargs': {
                **smoothing_kwargs(sampling_ms, sampling_count),
                **(subf_config or {}),
            }
        }
    }


def smoothing_trend_kwargs(
        sampling_ms,
        sampling_count,
        regression_count,
        delay_feature_s,
):
    """
    create feature kwargs for: sample, convert to ticks and perform moving average
    add sub feature of regression and delayed value comparison
    """
    return {
        'periodic_ms': sampling_ms,
        'periodic_timestamps': True,
        'value_preprocessors_config': [{
            'name': 'value_processor_to_tick',
        }],
        'value_processors_config': [{
            'name': 'value_processor_moving_average',
            'kwargs': {
                'n_entries': sampling_count
            },
        }],
        'sub_features_config': {
            # 'reg': {
            #     'name': 'RunnerFeatureSubRegression',
            #     'kwargs': {
            #         'element_count': regression_count,
            #     },
            # },
            'cmp': {
                'name': 'RunnerFeatureSubDelayComparison',
                'kwargs': {
                    'delay_seconds': delay_feature_s,
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


def ltp_window_kwargs(ltp_window_sampling_ms, ltp_window_width_s, ltp_window_sampling_count):
    return {
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


def subf_dif(subf_config, delay_s):
    return {
        KEY_DIFF: {
            'name': 'RunnerFeatureSubWindow',
            'kwargs': {
                'window_processors': [{
                    'name': 'value_processor_max_dif',
                }],
                'delay_seconds': delay_s,
                'outside_window': True,
                'sub_features_config': subf_config,
            },
        },
    }


def subf_tick(subf_config):
    return {
        KEY_TICKS: {
            'name': 'RunnerFeatureSub',
            'kwargs': {
                'value_processors_config': [{
                    'name': 'value_processor_to_tick',
                }],
                'sub_features_config': subf_config,
            },
        },
    }


def ltp_minmax(width_s):
    return {
        'min': {
            'name': 'RunnerFeatureSubWindow',
            'kwargs': {
                'window_processors': [{
                    'name': 'value_processor_min',
                }],
                'delay_seconds': width_s,
                'outside_window': True,
            }
        },
        'max': {
            'name': 'RunnerFeatureSubWindow',
            'kwargs': {
                'window_processors': [{
                    'name': 'value_processor_max',
                }],
                'delay_seconds': width_s,
                'outside_window': True,
            }
        },
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
        split_sum_s,
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
                'value_processors_config': [{
                    'name': 'value_processor_moving_average',
                    'kwargs': {
                        'n_entries': spread_sampling_count
                    }
                }],
            }
        },

        # 'bckdif': biggest_diff_feature(
        #     diff_s=diff_s,
        #     window_var='window_backs',
        #     window_func_key='window_func_best_back',
        # ),
        #
        # 'laydif': biggest_diff_feature(
        #     diff_s=diff_s,
        #     window_var='window_lays',
        #     window_func_key='window_func_best_lay'
        # ),
        #
        # 'ltpdif': biggest_diff_feature(
        #     diff_s=diff_s,
        #     window_var='window_ltps',
        #     window_func_key='window_func_ltp',
        # ),

        'lay': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': {
                'sub_features_config': {
                    **subf_tick(subf_dif(None, diff_s)),
                    **smoothing_sub(ladder_sampling_ms, ladder_sampling_count, None)
                },
            },
        },

        'bck': {
            'name': 'RunnerFeatureBestBack',
            'kwargs': {
                'sub_features_config': subf_tick(subf_dif(None, diff_s))
            }
        },

        'ltp': {
            'name': 'RunnerFeatureLTP',
            'kwargs': {
                'sub_features_config': ltp_minmax(ltp_window_width_s)
            }
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
            'name': 'RunnerFeatureBookSplitWindow',
            'kwargs': {
                'sub_features_config': {
                    'sum': {
                        'name': 'RunnerFeatureSubSum',
                        'kwargs': {
                            'delay_seconds': split_sum_s,
                            'outside_window': False,
                        },
                    },
                }
            }
        },

        # 'ltpmin': {
        #     'name': 'RunnerFeatureTradedWindowMin',
        #     'kwargs': ltp_window_kwargs(ltp_window_sampling_ms, ltp_window_width_s, ltp_window_sampling_count),
        # },

        # 'ltpmax': {
        #     'name': 'RunnerFeatureTradedWindowMax',
        #     'kwargs': ltp_window_kwargs(ltp_window_sampling_ms, ltp_window_width_s, ltp_window_sampling_count),
        # },

        'tv': {
            'name': 'RunnerFeatureTVTotal',
        },

        'bcksm': {
            'name': 'RunnerFeatureBestBack',
            'kwargs': smoothing_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
            )
        },

        'laysm': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': smoothing_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
            )
        },

        'ltpsm': {
            'name': 'RunnerFeatureLTP',
            'kwargs': smoothing_kwargs(
                ltp_sampling_ms,
                ltp_sampling_count,
            )
        },

        'bcksmt': {
            'name': 'RunnerFeatureBestBack',
            'kwargs': smoothing_trend_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
                ladder_regression_count,
                delay_feature_s,
            )
        },

        'laysmt': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': smoothing_trend_kwargs(
                ladder_sampling_ms,
                ladder_sampling_count,
                ladder_regression_count,
                delay_feature_s,
            )
        },

        'ltpsmt': {
            'name': 'RunnerFeatureLTP',
            'kwargs': smoothing_trend_kwargs(
                ltp_sampling_ms,
                ltp_sampling_count,
                ltp_regression_count,
                delay_feature_s,
            )
        },

    }

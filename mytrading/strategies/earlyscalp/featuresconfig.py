from typing import Dict


def get_scalp_feature_configs(
        n_ladder_elements,
        n_wom_ticks,
        hold_s,
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

    delayer_config = {
        "hold_delay": {
            "name": "RunnerFeatureSubConstDelayer",
            "kwargs": {
                "hold_seconds": hold_s,
            }
        }
    }

    return {

        'best back': {
            'name': 'RunnerFeatureBestBack',
            'kwargs': {
                'sub_features_config': delayer_config
            },
        },

        'best lay': {
            'name': 'RunnerFeatureBestLay',
            'kwargs': {
                'sub_features_config': delayer_config
            },
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

        'ltp': {
            'name': 'RunnerFeatureLTP',
        },

        'tv': {
            'name': 'RunnerFeatureTVTotal',
        },

        'wom': {
            'name': 'RunnerFeatureWOM',
            'kwargs': {
                'wom_ticks': n_wom_ticks
            },
        },

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
        }

    }

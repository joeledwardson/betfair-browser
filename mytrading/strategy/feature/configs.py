from typing import List, Dict, Optional
from myutils.myregistrar import MyRegistrar
import os, yaml
from os import path
from ...exceptions import FeatureConfigException

reg_features = MyRegistrar()


class ConfigDirHolder:
    def __init__(self, cfg_dir: str, out_dir, reg: MyRegistrar):
        self._cfg_dir = cfg_dir
        self._out_dir = out_dir
        self._reg = reg

    def reload(self):
        _, _, filenames = os.walk(self._cfg_dir)
        for fn in filenames:
            p_in = path.join(self._cfg_dir, fn)
            with open(p_in, 'r') as f:
                data = f.read()
            file_cfg = yaml.load(data, yaml.FullLoader)
            if 'name' not in file_cfg:
                raise FeatureConfigException(f'"name" not found in config path "{p_in}"')
            if 'kwargs' not in file_cfg:
                raise FeatureConfigException(f'"kwargs" not found in config path "{p_in}"')
            if type(file_cfg['kwargs']) is not dict:
                raise FeatureConfigException(f'"kwargs" item in "{p_in}" not dict')
            reg_nm = file_cfg.pop('name')
            reg_kwargs = file_cfg.pop('kwargs')
            if file_cfg:
                raise FeatureConfigException(f'"{p_in}" contains known keys: {file_cfg}')
            ftr_cfg = self._reg[reg_nm](**reg_kwargs)
            p_out = path.join(self._out_dir, fn)
            with open(p_out, 'w') as f:
                f.write(yaml.dump(ftr_cfg))


@reg_features.register_element
def features_config_spike(
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

    def ltp_win_kwargs(sample_ms, cache_count):
        d = {
            'sub_features_config': {
                'smp': {
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
                                    'kwargs': ltp_win_kwargs(ltp_window_sampling_ms, ltp_window_sampling_count)
                                },
                                'min': {
                                    'name': 'RFTVLadMin',
                                    'kwargs': ltp_win_kwargs(ltp_window_sampling_ms, ltp_window_sampling_count)
                                }
                            }
                        }
                    }
                }
            }
        },

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


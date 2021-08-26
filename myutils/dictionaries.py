from typing import Iterable, Dict
import copy
from collections.abc import Mapping
from .exceptions import DictException


def validate_config(cfg: Dict, cfg_spec: Dict):
    _cfg = copy.deepcopy(cfg)
    for k, spec in cfg_spec.items():
        exist = k in _cfg
        val = _cfg.pop(k, None)
        if not spec.get('optional'):
            if not exist:
                raise DictException(f'expected key "{k}" in configuration dict as per config spec: "{cfg_spec}"')
        if exist:
            # if 'type' in spec:
            if not isinstance(val, spec['type']):
                raise DictException(f'expected key "{k}" value to be type "{spec["type"]}", got "{type(val)}"')
    if _cfg:
        raise DictException(f'configuration dictionary has unexpected values: "{_cfg}"')


def is_dict_subset(x, y):
    """recursively determine if key value pairs in x are a subset of y"""
    for k, v in x.items():
        if k not in y:
            return False
        elif type(v) is dict:
            if not isinstance(y[k], Iterable):
                return False
            elif not is_dict_subset(v, y[k]):
                return False
        elif v != y[k]:
            return False
    return True


def dict_update(x: Mapping, y: Mapping):
    """recursively update key value pairs of y with x"""

    for k, v in x.items():

        if type(v) is not dict:
            # value is not dict
            y[k] = v
            continue

        # value is dict
        if k not in y:
            # value is dict & key not found in y
            y[k] = v
            continue

        # value is dict & key found in y
        if isinstance(y[k], Iterable):
            # value is dict & key found in y & value in y is iterable
            dict_update(v, y[k])
            continue

        # value is dict & key found in y & value in y is not iterable
        y[k] = v


def dict_sort(d: dict, key=lambda item: item[1]) -> Dict:
    """sort a dictionary items"""
    return {k: v for k, v in sorted(d.items(), key=key)}
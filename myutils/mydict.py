from typing import Iterable, Dict
import copy
from os import path
import os
import yaml
from .exceptions import DictException


def load_yaml_confs(cfg_dir: str) -> Dict:
    """get list of .yaml configs in a dictionary, key is file name, value is dict"""
    # check directory is set
    if type(cfg_dir) is not str:
        raise DictException(f'directory "{cfg_dir}" is not a string')

    # check actually exists
    if not path.isdir(cfg_dir):
        raise DictException(f'directory "{cfg_dir}" does not exist!')

    # dict of configs to return
    configs = dict()

    # get files in directory
    _, _, files = next(os.walk(cfg_dir))

    # loop files
    for file_name in files:

        # get file path and name without ext
        file_path = path.join(cfg_dir, file_name)
        name, ext = path.splitext(file_name)
        if ext != '.yaml':
            continue

        with open(file_path) as f:
            # The FullLoader parameter handles the conversion from YAML
            # scalar values to Python the dictionary format
            cfg = yaml.load(f, Loader=yaml.FullLoader)

        configs[name] = cfg

    return configs


def validate_config(cfg: Dict, cfg_spec: Dict):
    _cfg = copy.deepcopy(cfg)
    for k, spec in cfg_spec.items():
        exist = k in _cfg
        val = _cfg.pop(k, None)
        if not spec.get('optional'):
            if not exist:
                raise DictException(f'expected key "{k}" in configuration dict as per config spec: "{cfg_spec}"')
        if exist:
            exp_typ = spec['type']
            val_typ = type(val)
            if val_typ is not exp_typ:
                raise DictException(f'expected key "{k}" value to be type "{exp_typ}", got "{val_typ}"')
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


def dict_update(x: dict, y: Iterable):
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
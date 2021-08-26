import os
import re
from os import path
from typing import Dict

import yaml

from myutils.exceptions import DictException


def get_filepaths(target_path, file_pattern=None, dir_pattern=None):
    """
    get complete list of full file paths with a 'target_path' directory
    Can specify an optional 'file_pattern' regex to only match certain file names
    Can specify an optional 'dir_pattern' regex to match certain directory names
    """

    files = []

    for (dirpath, dirnames, filenames) in os.walk(target_path):
        for f in filenames:
            if file_pattern and not re.match(file_pattern, f):
                continue
            if dir_pattern:
                _, d = os.path.split(dirpath)
                if not re.match(dir_pattern, d):
                    continue
            files.append(os.path.join(dirpath, f))

    return files


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
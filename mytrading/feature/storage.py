from typing import Dict
from os import path, makedirs
from myutils.jsonfile import add_to_file, read_file
from ..utils.storage import EXT_FEATURE
from .utils import get_feature_data
from .features import RunnerFeatureBase


def get_feature_file_name(selection_id) -> str:
    """
    get file name to store feature data for a runner
    """
    return str(selection_id) + EXT_FEATURE


def features_to_file(file_path: str, features: Dict[str, RunnerFeatureBase]):
    """
    write runner dictionary of {feature name: feature instance} to file
    """

    # create dir in case not exist
    dir_path, _ = path.split(file_path)
    makedirs(dir_path, exist_ok=True)

    # get feature data into dictionary
    data = {}
    get_feature_data(data, features)

    # write to file, overwriting if already exist
    add_to_file(file_path, data, mode='w')


def features_from_file(file_path: str):
    """
    retrieve feature data sets from files
    """
    data = read_file(file_path)
    for entry in data:
        RunnerFeatureBase.post_de_serialize(entry)
    return data

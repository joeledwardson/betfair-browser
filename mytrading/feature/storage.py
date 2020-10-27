from typing import Dict
from os import path, makedirs
from myutils.jsonfile import add_to_file
from ..utils.storage import EXT_FEATURE
from .feature import RunnerFeatureBase


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

    data = {}

    # loop features and get data
    for feature_name, feature in features.items():
        fdata = feature.get_plotly_data()
        fdata = feature.pre_serialize(fdata)
        data[feature_name] = fdata

    # write to file, overwriting if already exist
    add_to_file(file_path, data, mode='w')

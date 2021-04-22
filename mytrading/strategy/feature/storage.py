from os import path, makedirs
import logging
from myutils.jsonfile import add_to_file, read_file_lines
from typing import List, Dict
from mytrading.utils.storage import EXT_FEATURE
from .utils import get_feature_data
from .features import RFBase

active_logger = logging.getLogger(__name__)


# TODO - depreciated?
def get_feature_file_name(selection_id) -> str:
    """
    get file name to store feature data for a runner
    """
    return str(selection_id) + EXT_FEATURE


# TODO - should be incremental in feature itself
def features_to_file(file_path: str, features: Dict[str, RFBase]):
    """
    write runner dictionary of {feature name: feature instance} to file
    """

    # create dir in case not exist
    dir_path, _ = path.split(file_path)
    makedirs(dir_path, exist_ok=True)

    # get feature data into dictionary
    data = get_feature_data(features, pre_serialize=True)

    # write to file, overwriting if already exist
    add_to_file(file_path, data, mode='w')


def features_from_file(file_path: str) -> Dict[str, List[Dict[str, List]]]:
    """
    retrieve feature data sets from files
    """

    # read from file
    data = read_file_lines(file_path)

    # check not empty
    if len(data) == 0:
        active_logger.critical(f'features read from file "{file_path}" is empty')
        return {}

    # take first element
    data = data[0]

    # loop feature data in dict
    for _, feature_data in data.items():

        # de-serialize timestamps
        RFBase.post_de_serialize(feature_data)

    return data

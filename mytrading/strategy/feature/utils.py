from typing import Dict
import logging
from betfairlightweight.resources import MarketBook

import numpy as np
from myutils.jsonfile import add_to_file
from .features import RFBase, ftrs_reg, BetfairFeatureException
from .window import Windows

active_logger = logging.getLogger(__name__)


# TODO - should be in __init__?
def generate_features(
        feature_configs: dict,
) -> Dict[str, RFBase]:
    """
    create dictionary of features based on a dictionary of `features_config`,
    - key: feature usage name
    - value: dict of
        - 'name': class name of feature
        - 'kwargs': dict of constructor arguments used when creating feature
    """
    features = dict()
    for name, conf in feature_configs.items():
        if type(conf) is not dict:
            active_logger.warning(f'feature "{name}" config not dict: {conf}')
            continue
        if 'name' not in conf:
            active_logger.warning(f'feature "{name}" does not have "name" attr')
            continue
        feature_class = ftrs_reg[conf['name']]
        kwargs = conf.get('kwargs', {})
        if type(kwargs) is not dict:
            active_logger.warning(f'features "{name}" kwargs not dict: {kwargs}')
            continue
        try:
            features[name] = feature_class(**kwargs, feature_key=name)
        except TypeError as e:
            raise BetfairFeatureException(
                f'error creating feature "{name}": {e}'
            )
    return features


# TODO - remove?, this is just writing JSON to a file
def write_feature_configs(
        feature_configs: dict,
        file_path: str,
        indent=4,
):
    """
    write a feature configuration to a JSON file

    Parameters
    ----------
    feature_configs :
    file_path :
    indent :

    Returns
    -------

    """
    add_to_file(file_path, feature_configs, mode='w', indent=indent)


# TODO - this should be a purely historic function where feature data is not deleted as generated
def get_feature_data(features: Dict[str, RFBase]):
    """
    recursively get plotly data from feature list (indexed by feature name)
    assign sub-feature data using '.' to indicate parent with feature naming

    return data dictionary
    """

    data = {}

    def inner(_features: Dict[str, RFBase]):

        # loop features and get data
        for ftr in _features.values():

            # # get plotly data
            # f_data = feature.get_plotly_data()
            #
            # # serialize if specified
            # if pre_serialize:
            #     f_data = feature.pre_serialize(f_data)

            # if parent name given, use it to prefix sub-name (e.g. for parent 'ltp' and name 'delay' it would be
            # 'ltp.delay')
            # if _parent_name:
            #     feature_name = '.'.join([_parent_name, feature_name])

            if len(ftr.out_cache):
                a = np.array(ftr.out_cache)
                data[ftr.ftr_identifier] = [{
                    'x': a[:, 0],
                    'y': a[:, 1]
                }]
            #
            #
            # # assign data to name key
            # data[feature_name] = f_data

            # call function recursively with sub features
            inner(_features=ftr.sub_features)

    inner(features)
    return data


# TODO - depreciated?
def get_max_buffer_s(
        features: Dict[str, RFBase],
) -> int:
    """
    get maximum number of seconds as delay from feature set for computations
    """

    # inner function for recursion
    def _get_delay(dly, ftrs):

        # loop features
        for ftr in ftrs.values():

            # update maximum delay
            dly = max(dly, ftr.cache_secs or 0)

            # loop sub-features
            dly = _get_delay(dly, ftr.sub_features)

        return dly

    return _get_delay(0, features)
from typing import Dict

from betfairlightweight.resources import MarketBook

from myutils.jsonfile import add_to_file
from .features import RunnerFeatureBase, features_dict
from .window import Windows


def generate_features(
        selection_id: int,
        book: MarketBook,
        windows: Windows,
        feature_configs: dict,
) -> Dict[str, RunnerFeatureBase]:
    """
    create dictionary of features based on a dictionary of `features_config`,
    - key: feature usage name
    - value: dict of
        - 'name': class name of feature
        - 'kwargs': dict of constructor arguments used when creating feature
    """
    features = dict()
    for name, conf in feature_configs.items():
        feature_class = features_dict[conf['name']]
        features[name] = feature_class(**conf.get('kwargs', {}))
        features[name].race_initializer(selection_id, book, windows)
    return features


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


def get_feature_data(
        data: Dict,
        features: Dict[str, RunnerFeatureBase],
        parent_name='',
        pre_serialize=True
):
    """
    recursively get plotly data from feature list (indexed by feature name)
    assign feature data to 'data' dictionary with feature name
    assign sub-feature data using '.' to indicate parent with feature naming

    pass empty dictionary to function for it to set attributes
    """

    # loop features and get data
    for feature_name, feature in features.items():

        # get plotly data
        f_data = feature.get_plotly_data()

        # serialize if specified
        if pre_serialize:
            f_data = feature.pre_serialize(f_data)

        # if parent name given, use it to prefix sub-name (e.g. for parent 'ltp' and name 'delay' it would be
        # 'ltp.delay')
        if parent_name:
            feature_name = '.'.join([parent_name, feature_name])

        # assign data to name key
        data[feature_name] = f_data

        # call function recursively with sub features
        get_feature_data(data, feature.sub_features, parent_name=feature_name, pre_serialize=pre_serialize)


def get_max_buffer(
        features: Dict[str, RunnerFeatureBase],
) -> int:
    """
    get maximum number of seconds as delay from feature set for computations

    Parameters
    ----------
    features :

    Returns
    -------

    """

    # inner function for recursion
    def _get_delay(dly, ftrs):

        # loop features
        for ftr in ftrs.values():

            # update maximum delay
            dly = max(dly, ftr.computation_buffer_seconds())

            # loop sub-features
            dly = _get_delay(dly, ftr.sub_features)

        return dly

    return _get_delay(0, features)
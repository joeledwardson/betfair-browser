from typing import Dict, List
import pandas as pd
from myutils import myregistrar
from pandas.core.base import DataError
from .formatprocessors import format_processors
from functools import partial
import logging


plt_procs = myregistrar.MyRegistrar()
active_logger = logging.getLogger(__name__)


class FigureProcessorException(Exception):
    pass


# TODO - these should probably be in a class so can store data
def process_plotly_data(
        data: Dict,
        features_data: Dict[str, List[Dict[str, List]]],
        processors_config: List[Dict]
):
    """
    use plotly data processors to process data
    """
    for i, cfg in enumerate(processors_config):
        func = plt_procs[cfg['name']]
        kwargs = cfg.get('kwargs', {})
        try:
            data = func(data, features_data, **kwargs)
        except (TypeError, ValueError, DataError) as e:
            raise FigureProcessorException(
                f'error processing figure data, cfg #{i} in func "{cfg["name"]}" with kwargs "{kwargs}": {e}'
            )
    return data


def remove_duplicates(data: pd.Series) -> pd.Series:
    """
    remove duplicates from series with datetime index keeping last value
    """
    return data[~data.index.duplicated(keep='last')]


@plt_procs.register_element
def plotly_df_to_data(data: pd.DataFrame, features_data) -> Dict:
    """
    convert dataframe to dictionary (assuming columns are appropriate for plotly chart arg) and use index for 'x' vals
    """
    values = data.to_dict(orient='list')
    values.update({'x': data.index})
    return values


@plt_procs.register_element
def plotly_series_to_data(data: pd.Series, features_data) -> Dict:
    """
    convert series to dictionary with 'x' and 'y'
    """
    return {
        'x': data.index,
        'y': data.to_list()
    }


# TODO - need anymore?
@plt_procs.register_element
def plotly_regression(data: Dict, features_data) -> Dict:
    """
    convert returned values dict from 'RunnerFeatureRegression' feature into plotly compatible dict with 'x',
    'y' and 'text'
    """

    # 'rsquared' should be a single value in dictionary in which to create text from
    txt_rsqaured = f'rsquared: {data["rsquared"]:.2f}'

    # return x and y coordinate lists with repeated text string indicating rsqaured value
    return {
        'x': data['x'],
        'y': data['predicted'],
        'text': [txt_rsqaured for x in data['x']]
    }


@plt_procs.register_element
def plotly_values_resampler(data: pd.DataFrame, features_data, n_seconds, agg_function) -> pd.DataFrame:
    """
    resample 'df' DataFrame for 'n_seconds', using last value each second and forward filling
    can override default sampling function 'last' with `sampling_function` arg
    """
    rule = f'{n_seconds}S'
    return data.resample(rule).agg(agg_function) if data.shape[0] else data


@plt_procs.register_element
def plotly_values_rolling(data: pd.DataFrame, features_data, n_seconds, agg_function) -> pd.DataFrame:
    rule = f'{n_seconds}S'
    return data.rolling(rule).agg(agg_function) if data.shape[0] else data


@plt_procs.register_element
def plotly_data_to_series(data: Dict, features_data) -> pd.Series:
    """
    convert 'data' x-y plotly values (dict with 'x' and 'y' indexed list values) to pandas series where index is 'x'
    """
    return pd.Series(data['y'], index=data['x'])


@plt_procs.register_element
def data_nptype(data, features_data, data_types):
    for k, v in data_types.items():
        data[k] = data[k].astype(v)
    return data



@plt_procs.register_element
def plotly_set_attrs(
        data: Dict,
        features_data: Dict[str, List[Dict[str, List]]],
        attr_configs: List[Dict],
) -> pd.DataFrame:
    """
    adds a different feature's data to the current feature plotly data

    Parameters
    ----------
    data :
    features_data :
    attr_configs: list of feature config dicts whose data to collect, whose attributes include:
             - 'feature_name' : name of the feature whose' data to append to existing `data` dict (used as key to
             `features_data`) note that only the **first** of the list of data from the feature is used TODO (improve)
            - 'attr_names': list of plotly attribute names to set with feature values (e.g. ['color'])
            - feature_value_processors (optional): list of 'value_processors' whose signature should be identical to
            those used in configuration in ..\config.py

    Returns
    -------

    """

    # convert data to pandas series
    sr_data = plotly_data_to_series(data, features_data)

    # remove duplicate datetime indexes from each series or pandas winges when trying to make a dataframe
    sr_data = remove_duplicates(sr_data)

    # create dictionary to use for dataframe, starting with trace output 'y' with base values (plotly features will
    # be added later in function from additional feature)
    df_data = {
        'y': sr_data,
    }

    # check has x and y values
    if not ('y' in data and len(data['y']) and 'x' in data and len(data['x'])):

        active_logger.warning('either x or y data is empty when trying to set attribute')

        # if don't, just return pandas dataframe now without adding attributes
        return pd.DataFrame(df_data)

    # check haven't forgotten [] braces and passed a dict by mistake
    assert(type(attr_configs) is list)

    # loop feature configurations
    for cfg in attr_configs:

        # get attributes from configuration dict
        feature_name = cfg['feature_name']
        attr_names = cfg['attr_names']
        assert(type(attr_names) == list)
        feature_value_processors = cfg.get('feature_value_processors')

        if feature_name not in features_data:
            active_logger.warning(f'feature "{feature_name}" not found in feature data')
            continue

        # get data from feature using feature name as key
        attr_data = features_data[feature_name]

        # check feature data list is not empty
        if len(attr_data) == 0:
            continue

        # take first data set in list
        attr_data = attr_data[0]

        # process feature data if processors passed
        if feature_value_processors is not None:

            # perform nested run of data processors (process_plotly_data() is called to reach current execution point),
            # on the feature data
            attr_data = process_plotly_data(attr_data, features_data, feature_value_processors)

        # create series from feature data
        sr_attr = pd.Series(attr_data['y'], index=attr_data['x'])

        # remove duplicates (otherwise pandas singes when trying to create dataframe)
        sr_attr = remove_duplicates(sr_attr)

        # assign to attribute names
        for name in attr_names:
            df_data[name] = sr_attr

    # create dataframe with using dictionary with additional plotly attributes set from feature data
    df = pd.DataFrame(df_data)
    return df


@plt_procs.register_element
def plotly_df_formatter(data: pd.DataFrame, features_data, formatter_name, df_column, formatter_kwargs: Dict=None):
    """
    apply a value formatter to a column in a pandas dataframe

    Parameters
    ----------
    data :
    features_data :
    formatter_name :
    df_column : column in pandas dataframe to apply to
    formatter_kwargs : dictionary of kwargs to apply to formatter function

    Returns
    -------

    """

    # set formatter kwargs to empty dictionary if not passed
    if formatter_kwargs is None:
        formatter_kwargs = {}

    # get formatter function from dictionary
    formatter = format_processors[formatter_name]

    # generate partial function using formatter kwargs and function
    f = partial(formatter, **formatter_kwargs)

    if df_column in data.columns:

        # apply function to column values
        data[df_column] = data[df_column].apply(f)

    else:

        active_logger.warning(f'column "{df_column}" does not exist in dataframe columns: {data.columns.tolist()}')

    return data


@plt_procs.register_element
def plotly_df_fillna(data: pd.DataFrame, features_data, method='ffill'):
    return data.fillna(method=method)


@plt_procs.register_element
def plotly_df_diff(data: pd.DataFrame, features_data):
    return data.diff()


@plt_procs.register_element
def plotly_df_text_join(data: pd.DataFrame, features_data, dest_col: str, source_cols: List[str]) -> pd.DataFrame:
    """
    join multiple text columns to form a single text column and remove source cols
    """
    # check not empty
    if not data.shape[0]:
        return data

    # select non-empty cols
    cols = []
    for col in source_cols:
        if col in data.columns:
            cols.append(col)
        else:
            active_logger.warning(f'column {col} not found in columns')

    if cols:

        # fill blank text entries
        data[cols] = data[cols].fillna('')

        # join using HTML newline character text columns into destination column
        data[dest_col] = data[cols].agg('<br>'.join, axis=1)

        # drop source columns
        data = data.drop(cols, axis=1)

    return data



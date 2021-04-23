from typing import Dict, List, Optional
import pandas as pd
from myutils import myregistrar
from pandas.core.base import DataError
from .formatprocessors import format_processors
from functools import partial
import logging
from plotly import graph_objects as go
import yaml
from collections import deque
import numpy as np


plt_procs = myregistrar.MyRegistrar()
active_logger = logging.getLogger(__name__)


class FigureException(Exception):
    pass
class FigureDataProcessorException(FigureException):
    pass
class FigurePostProcessException(FigureException):
    pass
class FigEmptyException(FigureException):
    pass


# TODO - ok new design principle, each processor can have a "key_in" and "key_out" variables which dictate which
#  variable to use in new dictionary buffer. data can be loaded into a key "data" and by default "key_in" is set to
#  "data" unless specified otherwise, and output from processor is by default loaded to "data" key again by setting
#  "key_out" to "data" unless specified otherwise. 'features_data' should be held in the class itself and accessed
#  via processors that way by passing via argument
# TODO - actually would be easier if there was a separate dict in configuration document called 'keys' with an 'in'
#  and 'out' members


class FigPostProcessor:
    """post process a plotly figure"""
    def __init__(self, fig: go.Figure, prc_config: List[Dict]):
        self.fig = fig
        self.prc_config = prc_config
        if type(prc_config) is not list:
            raise FigurePostProcessException(f'figure config "{prc_config}" is not list')

    def process(self):
        """use plotly data processors to process data"""
        for i, cfg in enumerate(self.prc_config):
            active_logger.info(f'invoking fig post process: #{i}')
            if type(cfg) is not dict:
                raise FigurePostProcessException(f'config "{cfg}" is not dict')
            if 'name' not in cfg:
                raise FigurePostProcessException(f'config does not have "name" key')
            name = cfg['name']
            active_logger.info(f'fig process name: {name}')
            if not hasattr(self, name):
                raise FigurePostProcessException(f'process "{name}" not recognised')
            func = getattr(self, name)
            kwargs = cfg.get('kwargs', {})
            active_logger.info(f'fig kwargs:\n{yaml.dump(kwargs)}')
            func(self.fig, **kwargs)

    def prc_plotlygroup(self, t_name,  t_group: str):
        """group a set of plotly traces with a unified name to a single legend"""
        # filter to traces with name
        for i, trace in enumerate([t for t in self.fig.data if t['name'] == t_name]):
            # show legend on first trace but ignore others, group name together
            trace['legendgroup'] = t_group
            if i == 0:
                trace['showlegend'] = True
            else:
                trace['showlegend'] = False


class FigDataProcessor:
    """process feature data in a figure"""
    DEF_KEY = 'key_default'
    NEWLINE = '<br>'

    def __init__(self, ftr_key, features_data, prc_config):
        self.ftr_key = ftr_key
        self.features_data = features_data
        self.prc_config = prc_config
        active_logger.info(f'creating figure data processor for feature "{ftr_key}"')
        if ftr_key not in features_data:
            raise FigureDataProcessorException(f'no feature "{ftr_key}" in features data')
        data = features_data[ftr_key]
        self.buf = {
            self.DEF_KEY: data
        }
        if type(prc_config) is not list:
            raise FigureDataProcessorException(f'processor config "{prc_config}" is not list')

    def process(self):
        active_logger.info(f'processing feature "{self.ftr_key}"')
        key_out = ''
        for i, cfg in enumerate(self.prc_config):
            active_logger.info(f'invoking fig process: #{i}')
            if type(cfg) is not dict:
                raise FigureDataProcessorException(f'config "{cfg}" is not dict')
            if 'name' not in cfg:
                raise FigureDataProcessorException(f'config does not have "name" key')
            name = cfg['name']
            active_logger.info(f'fig process name: {name}')
            kwargs = cfg.get('kwargs', {})
            keys = kwargs.get('keys', {})
            key_in = keys.get('key_in', self.DEF_KEY)
            key_out = keys.get('key_out', self.DEF_KEY)
            if not hasattr(self, name):
                raise FigureDataProcessorException(f'no processor "{name}" found')
            func = getattr(self, name)
            try:
                input_data = self.buf[key_in]
                new_data = func(input_data, **kwargs)
                self.buf[key_out] = new_data
            except (TypeError, ValueError, DataError) as e:
                raise FigureDataProcessorException(
                    f'error processing figure data, cfg #{i} in func "{cfg["name"]}" with kwargs "{kwargs}": {e}'
                )
        return self.buf[key_out]

    def prc_datatodf(self, data: dict, data_col: str) -> pd.DataFrame:
        """create dataframe from data dictionary, specify dataframe col"""
        if not len(data['x']):
            raise FigEmptyException
        return pd.DataFrame({data_col: data['y']}, index=data['x'])

    def prc_ftrtodf(self, data, ftr_key: str, data_col: str) -> pd.DataFrame:
        """create dataframe from a different feature"""
        if ftr_key not in self.features_data:
            raise FigureDataProcessorException(f'feature "{ftr_key}" not in data')
        return self.prc_datatodf(
            data=self.features_data[ftr_key],
            data_col=data_col
        )

    def prc_dfconcat(self, data, buf_keys: List[str], concat_kwargs: Optional[Dict]) -> pd.DataFrame:
        """concatenate dataframes from buffer together"""
        concat_kwargs = concat_kwargs or {}
        return pd.concat([self.buf[k] for k in buf_keys], **concat_kwargs)

    def prc_dftodict(self, data: pd.DataFrame, orient='list', key_index='x') -> Dict:
        """convert dataframe to dictionary and add index as keyed value"""
        values = data.to_dict(orient=orient)
        if key_index:
            values.update({key_index: data.index})
        return values

    def prc_dffmtps(self, data: pd.DataFrame, df_col) -> pd.DataFrame:
        """format dataframe price-size column values"""
        if df_col not in data.columns:
            raise FigureDataProcessorException(f'column "{df_col}" not found in df')
        def fmt_ps(value):
            return self.NEWLINE.join([
                f'price: {ps["price"]}, size: £{ps["size"]:.2f}'
                for ps in value
            ])
        data[df_col] = data[df_col].apply(fmt_ps)
        return data

    def prc_dffillna(self, data: pd.DataFrame, method='ffill'):
        """fill N/A in dataframe"""
        return data.fillna(method=method)

    def prc_dffmtstr(self, data: pd.DataFrame, df_col: str, fmt_spec: str):
        """apply a string value formatter with single positional arg of value column in dataframe"""
        if df_col not in data.columns:
            raise FigureDataProcessorException(f'column "{df_col}" not found in df')

        def fmt(val):
            return fmt_spec.format(val)

        data[df_col] = data[df_col].apply(fmt)
        return data

    def prc_dfdiff(self, data: pd.DataFrame) -> pd.DataFrame:
        """apply difference of rows dataframe function"""
        return data.diff()

    def prc_dftypes(self, data, dtypes: Dict) -> pd.DataFrame:
        """set column name -> data type pairs in dataframe"""
        for k, v in dtypes.items():
            data[k] = data[k].astype(v)
        return data

    def prc_resmp(self, data: pd.DataFrame, n_seconds, agg_function) -> pd.DataFrame:
        """resample DataFrame over number of seconds period specifying an aggregate function"""
        rule = f'{n_seconds}S'
        return data.resample(rule).agg(agg_function)

# TODO - remove plotly specific references
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
        active_logger.info(f'invoking fig process #{i} with name {cfg.get("name")}')
        func = plt_procs[cfg['name']]
        kwargs = cfg.get('kwargs', {})
        try:
            new_data = func(data, features_data, **kwargs)
            data = new_data
        except (TypeError, ValueError, DataError) as e:
            raise FigureDataProcessorException(
                f'error processing figure data, cfg #{i} in func "{cfg["name"]}" with kwargs "{kwargs}": {e}'
            )
    return data



def remove_duplicates(data: pd.Series) -> pd.Series:
    """remove duplicates from series with datetime index keeping last value"""
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
    """convert series to dictionary with 'x' and 'y'"""
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

    # check has x and y values, if don't, just return pandas dataframe now without adding attributes
    if not ('y' in data and len(data['y']) and 'x' in data and len(data['x'])):
        active_logger.warning('either x or y data is empty when trying to set attribute')
        return pd.DataFrame(df_data)

    # check haven't forgotten [] braces and passed a dict by mistake
    assert(type(attr_configs) is list)

    # loop feature configurations
    for cfg in attr_configs:

        # get attributes from configuration dict
        feature_name = cfg['feature_name']
        attr_names = cfg['attr_names']
        if type(attr_names) is not list:
            pass # TODO - what is this?
        feature_value_processors = cfg.get('feature_value_processors')

        if feature_name not in features_data:
            raise FigureDataProcessorException(f'feature "{feature_name}" not found in feature data')

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

    # apply function to column values
    if df_column in data.columns:
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



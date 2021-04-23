from typing import Dict, List, Optional
import pandas as pd
from pandas.core.base import DataError
import logging
from plotly import graph_objects as go

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
            func(self.fig, **kwargs)

    def prc_plotlygroup(self, t_name, t_group: str):
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

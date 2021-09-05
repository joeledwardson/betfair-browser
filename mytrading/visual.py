from pandas.core.base import DataError
import yaml
from datetime import timedelta, datetime
from typing import List, Dict
import logging

from os import path, makedirs
from typing import Optional
import copy
import pandas as pd
from plotly import graph_objects as go
from plotly.subplots import make_subplots

from .exceptions import FigureException, FigureDataProcessorException, FigurePostProcessException
from mytrading.strategy.messages import format_message, MessageTypes
from .process.ticks import LTICKS_DECODED
from .process import closest_tick
from myutils import general


active_logger = logging.getLogger(__name__)


class FigPostProcessor:
    """post process a plotly figure"""

    def __init__(self, fig: go.Figure, prc_config: List[Dict]):
        self.fig = fig
        self.prc_config = prc_config
        if type(prc_config) is not list:
            raise FigurePostProcessException(f'figure config "{prc_config}" is not list')

    def process(self):
        """use plotly data processors to process data"""
        for i, _cfg in enumerate(self.prc_config):
            cfg = copy.deepcopy(_cfg)  # dont want to modify configurations dict by popping values
            active_logger.info(f'invoking fig post process: #{i}')
            if type(cfg) is not dict:
                raise FigurePostProcessException(f'config "{cfg}" is not dict')
            if 'name' not in cfg:
                raise FigurePostProcessException(f'config does not have "name" key')
            name = cfg.pop('name')
            active_logger.info(f'fig process name: {name}')
            if not hasattr(self, name):
                raise FigurePostProcessException(f'process "{name}" not recognised')
            func = getattr(self, name)
            kwargs = cfg.pop('kwargs', {})
            func(self.fig, **kwargs)
            if cfg:
                raise FigurePostProcessException(f'unrecognised elements in process: "{cfg}"')

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
    DEF_KEY = 'key_0'
    NEWLINE = '<br>'

    DEF_CFG = [{
        'name': 'prc_srtodict'
    }]  # by default convert feature data series to dictionary of 'x' and 'y' lists

    def __init__(self, ftr_key, features_data, prc_config):
        if not prc_config:
            prc_config = self.DEF_CFG
        active_logger.info(f'creating figure data processor for feature "{ftr_key}"')
        if ftr_key not in features_data:
            raise FigureDataProcessorException(f'no feature "{ftr_key}" in features data')
        data = features_data[ftr_key]
        self.buf = {
            self.DEF_KEY: data
        }
        if type(prc_config) is not list:
            raise FigureDataProcessorException(f'processor config "{prc_config}" is not list')
        self.ftr_key = ftr_key
        self.features_data = features_data
        self.prc_config = prc_config

    def process(self):
        active_logger.info(f'processing feature "{self.ftr_key}" with {len(self.prc_config)} configs')
        key_out = self.DEF_KEY
        for i, _cfg in enumerate(self.prc_config):
            cfg = copy.deepcopy(_cfg)  # don't want to modify configurations dict by popping values
            active_logger.info(f'invoking fig process: #{i}')
            if type(cfg) is not dict:
                raise FigureDataProcessorException(f'config "{cfg}" is not dict')
            if 'name' not in cfg:
                raise FigureDataProcessorException(f'config does not have "name" key')
            name = cfg.pop('name')
            active_logger.info(f'fig process name: {name}')
            kwargs = cfg.pop('kwargs', {})
            keys = cfg.pop('keys', {})
            if cfg:
                raise FigureDataProcessorException(f'config dict "{cfg}" still has values')
            key_in = keys.pop('key_in', self.DEF_KEY)
            key_out = keys.pop('key_out', self.DEF_KEY)
            if keys:
                raise FigureDataProcessorException(f'keys dict "{keys}" still has elements')
            if not hasattr(self, name):
                raise FigureDataProcessorException(f'no processor "{name}" found')
            func = getattr(self, name)
            try:
                input_data = self.buf[key_in]
                new_data = func(input_data, **kwargs)
                self.buf[key_out] = new_data
            except (TypeError, ValueError, DataError) as e:
                raise FigureDataProcessorException(
                    f'error processing figure data, cfg #{i} in func "{name}" with kwargs\n'
                    f'{yaml.dump(kwargs)}\n{e}'
                )
        return self.buf[key_out]

    def prc_srtodict(self, data: pd.Series, idx_key='x', val_key='y') -> Dict:
        """convert pandas data series to dictionary of 'x' and 'y' lists"""
        return {
            idx_key: data.index.tolist(),
            val_key: data.values.tolist()
        }

    def prc_getftr(self, data, ftr_key) -> pd.Series:
        """retrieve feature"""
        if ftr_key not in self.features_data:
            raise FigureDataProcessorException(f'feature "{ftr_key}" not in data')
        return self.features_data[ftr_key]

    def prc_ftrstodf(self, data, ftr_keys: dict) -> pd.DataFrame:
        """create dataframe from multiple features specified by dictionary of (df col => feature key)"""
        d = {}
        for df_col, k in ftr_keys.items():
            if k not in self.features_data:
                raise FigureDataProcessorException(f'feature "{k}" not found')
            d[df_col] = self.features_data[k]
        df = pd.DataFrame(d)
        return df

    def prc_buftodf(self, data, buf_cfg: Dict) -> pd.DataFrame:
        """concatenate series from buffer into dataframe, specified by (column name => buffer key)"""
        for k in buf_cfg.values():
            if k not in self.buf:
                raise FigureDataProcessorException(f'buffer key "{k}" not found')
        return pd.DataFrame({
            df_col: self.buf[k]
            for df_col, k in buf_cfg.items()
        })

    def prc_bufdfcat(self, data, buf_keys: List[str], axis=1, concat_kwargs: Optional[Dict] = None) -> pd.DataFrame:
        """concatenate dataframes from buffer together"""
        concat_kwargs = concat_kwargs or {}
        for k in buf_keys:
            if k not in self.buf:
                raise FigureDataProcessorException(f'buffer key "{k}" not found')
        return pd.concat([self.buf[k] for k in buf_keys], axis=axis, **concat_kwargs)

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

    def prc_dfcp(self, data: pd.DataFrame, col_src, col_out) -> pd.DataFrame:
        """copy a dataframe column"""
        data[col_out] = data[col_src]
        return data

    def prc_dftxtjoin(self, data: pd.DataFrame, src_cols, dest_col) -> pd.DataFrame:
        """join columns of dataframe together as text on separate lines"""
        def txtjoin(vals):
            return self.NEWLINE.join([str(v) for v in vals])
        data[dest_col] = data[src_cols].apply(txtjoin, axis=1)
        return data

    def prc_dfdrop(self, data: pd.DataFrame, cols) -> pd.DataFrame:
        """drop dataframe columns"""
        return data.drop(cols, axis=1)


class FeatureFigure:
    DEFAULT_PLOT_CFG = {
        'chart': 'Scatter',
        'chart_args': {
            'mode': 'lines'
        },
        'trace_args': {},
        'y_axis': 'odds',
    }
    DEFAULT_ORDER_CFG = {
        'trace_args': {},
        'chart_args': {
            'marker_size': 10,
        }
    }
    VERTICAL_SPACING = 0.05

    @staticmethod
    def get_chart_start(display_seconds: float, market_time: datetime, first: datetime) -> datetime:
        """get start of display chart, either specified time from market start or first market book"""
        if display_seconds:
            return market_time - timedelta(seconds=display_seconds)
        else:
            return first

    @staticmethod
    def modify_start(chart_start: datetime, orders_df: pd.DataFrame, buffer_seconds: float) -> datetime:
        """set start time to first order info update received minus buffer, if less than existing chart start"""
        if orders_df.shape[0]:
            orders_start = orders_df.index[0]
            orders_start = orders_start - timedelta(seconds=buffer_seconds)
            return min(orders_start, chart_start)
        return chart_start

    @staticmethod
    def modify_end(chart_end: datetime, orders_df: pd.DataFrame, buffer_seconds: float) -> datetime:
        """
        set end time to last order info update minus received buffer, if more than existing chart end
        removes market close from data frame when looking at last order timestamp
        """
        if orders_df.shape[0]:
            trimmed_orders = orders_df[orders_df['msg_type'] != MessageTypes.MSG_MARKET_CLOSE.name]
            if trimmed_orders.shape[0]:
                orders_end = trimmed_orders.index[-1]
                orders_end = orders_end + timedelta(seconds=buffer_seconds)
                return max(orders_end, chart_end)
        return chart_end

    @staticmethod
    def get_axisnames(cfgs: dict, def_yaxis: str) -> List[str]:
        """get list of yaxis names from default configuration and list of feature configurations"""
        return list(set(
            [def_yaxis] + [
                cfg.get('y_axis', def_yaxis)
                for cfg in cfgs.values()
            ]
        ))

    @staticmethod
    def create_figure(axisnames: List[str], vertical_spacing) -> go.Figure:
        """create chart with subplots based on 'y_axis' properties of feature plot configurations"""

        n_cols = 1
        n_rows = len(axisnames)

        return make_subplots(
            cols=n_cols,
            rows=n_rows,
            shared_xaxes=True,
            specs=[
                [
                    {'secondary_y': True} for y in range(n_cols)
                ] for x in range(n_rows)
            ],
            vertical_spacing=vertical_spacing
        )

    @staticmethod
    def fig_to_file(fig: go.Figure, file_path, mode='a'):
        """
        write a plotly figure to a file, default mode appending to file
        """
        d, _ = path.split(file_path)
        makedirs(d, exist_ok=True)
        with open(file_path, mode) as f:
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        active_logger.info(f'writing figure to file "{file_path}"')

    def __init__(
            self,
            ftrs_data: Dict[str, pd.Series],
            plot_cfg: Dict[str, Dict],
            title: str,
            chart_start: datetime,
            chart_end: datetime,
            orders_df: Optional[pd.DataFrame] = None,
            orders_cfg=None
    ):
        """
        create figure using default features for historical record list and a selected runner ID
        - records: list of historical records
        - features: dict of {feature name: feature instance} to apply
        - feature_plot_configs: dict of {feature name: feature plot config} to apply when plotting each feature
        - selection_id: id of runner
        - title: title to apply to chart
        - display_s: number of seconds before start time to display chart for, 0 indicates ignore
        - orders_df: dataframe of order update to add as annotated scatter points
        """
        # copy config so don't modify original
        fpc = copy.deepcopy(plot_cfg)

        # create figure based off axis names with correct number of subplots
        axis_names = self.get_axisnames(fpc, self.DEFAULT_PLOT_CFG['y_axis'])
        self.fig = self.create_figure(axis_names, vertical_spacing=self.VERTICAL_SPACING)

        # trim feature data
        ftrs_data = {
            nm: ftr[
                (ftr.index >= chart_start) &
                (ftr.index <= chart_end)
            ]
            for nm, ftr in ftrs_data.items()
        }

        # loop features, pop configuration and add trace
        for i, ftr_name in enumerate(ftrs_data.keys()):
            active_logger.info(f'plotting feature #{i}, name: "{ftr_name}"')
            cfg = fpc.pop(ftr_name, {})
            self.ftr_trace(self.fig, ftrs_data, ftr_name, axis_names, cfg)

        if fpc:
            raise FigureException(f'figure configuration still contains keys: "{list(fpc.keys())}"')

        # if order info dataframe passed and not empty then plot
        if orders_df is not None and orders_df.shape[0]:
            active_logger.info(f'trimming orders dataframe of {orders_df.shape[0]} elements')
            _odf = orders_df[
                (orders_df.index >= chart_start) &
                (orders_df.index <= chart_end)
            ]
            if _odf.shape[0]:
                active_logger.info(f'plotting trimmed orders dataframe of {_odf.shape[0]} elements')
                self.plot_orders(self.fig, _odf.copy(), orders_cfg)
            else:
                active_logger.info(f'trimmed orders has no elements, igorning...')

        # set figure layouts and return
        self.set_figure_layout(self.fig, title, chart_start, chart_end)

    def show(self, *args, **kwargs):
        self.fig.show(*args, **kwargs)

    @classmethod
    def ftr_trace(
            cls,
            fig: go.Figure,
            ftrs_data: Dict[str, pd.Series],
            ftr_name: str,
            axis_names: List[str],
            plot_cfg: Dict):
        """create trace from feature data and add to figure"""
        # if told to ignore feature then exit
        if plot_cfg.get('ignore'):
            active_logger.info(f'ignoring...')
            return

        # get y-axis name or default - and produce grid row index (starting from 1)
        axis_name = plot_cfg.pop('y_axis', cls.DEFAULT_PLOT_CFG['y_axis'])
        row = axis_names.index(axis_name) + 1

        # plotly chart function, chart kwargs, trace kwargs updating with grid row and (single column)
        chart_name = plot_cfg.pop('chart', cls.DEFAULT_PLOT_CFG['chart'])
        chart_args = plot_cfg.pop('chart_args', cls.DEFAULT_PLOT_CFG['chart_args'])
        trace_args = plot_cfg.pop('trace_args', cls.DEFAULT_PLOT_CFG['trace_args'])
        trace_args.update({'col': 1, 'row': row})
        value_processors = plot_cfg.pop('value_processors', [])

        # extract feature data from dictionary using feature key `ftr_name`, then feature data processors
        prc = FigDataProcessor(ftr_name, ftrs_data, value_processors)
        trace_data = prc.process()

        # use trace name identified by `rename` if specified, otherwise feature name
        nm = plot_cfg.pop('rename', ftr_name)

        # create plotly chart instance with feature data and add to plotly figure
        chart_func = getattr(go, chart_name)
        chart = chart_func(dict(name=nm) | trace_data | chart_args)
        fig.add_trace(chart, **trace_args)

        # run figure post processors
        post_prc = FigPostProcessor(fig, plot_cfg.pop('fig_post_processors', []))
        post_prc.process()
        if plot_cfg:
            raise FigureException(f'plot configuration has unrecognised values: "{plot_cfg}"')

    @classmethod
    def plot_orders(cls, fig: go.Figure, orders_df: pd.DataFrame, display_config=None, show_trade_id=True):
        """add dataframe of order information to plot"""
        if 'msg_type' not in orders_df.columns:
            raise FigureException('"msg_type" not found in orders dataframe, aborting')

        if 'msg_attrs' not in orders_df.columns:
            raise FigureException('"msg_attrs" not found in orders dataframe, aborting')

        # replace blank trade ID so they are not ignored by pandas groupby
        orders_df['trade_id'] = orders_df['trade_id'].fillna('0')

        # use message formatter to convert message type and attributes into single string message
        orders_df['msg'] = orders_df[['msg_type', 'msg_attrs']].apply(
            lambda cols: format_message(cols[0], cols[1]),
            axis=1
        )

        # check for messages equal to None (indicates that message formatter not returning a value)
        for row in orders_df[orders_df['msg'].isnull()].iterrows():
            raise FigureException(f'found row with message type "{row[1].get("msg_type")}" has no message!')

        # convert multi-line message ASCII \n newline characters into HTML newline characters <br>
        def tohtml(s):
            return FigDataProcessor.NEWLINE.join(s.split('\n'))

        orders_df['msg'] = orders_df['msg'].apply(tohtml)

        # get default configuration if not passed
        display_config = display_config or cls.DEFAULT_ORDER_CFG

        # loop groups but dont sort - pandas splits into iterators of (grouped value, dataframe)
        for i, (trade_id, df) in enumerate(orders_df.groupby(['trade_id'], sort=False)):

            # group dataframe by index (timestamps), where there are updates at the same timestamp
            grouped_df = df.groupby(df.index)

            # combine overlapping messages at timestamp by joining with newline
            msgs = grouped_df['msg'].apply(FigDataProcessor.NEWLINE.join)

            # take last of display odds and trade ID within each timestamp to display
            display_odds = grouped_df['display_odds'].last()
            trade_ids = grouped_df['trade_id'].last()

            # combine messages, display odds and trade ID in dataframe
            df = pd.concat([msgs, display_odds, trade_ids], axis=1)

            # if messages are to contain trade ID, then format trade ID with messages
            def join_trade(row):
                return 'trade ID: {}{}{}'.format(
                    row['trade_id'],
                    FigDataProcessor.NEWLINE,
                    row["msg"]
                )

            if show_trade_id:
                df['msg'] = df[['trade_id', 'msg']].apply(join_trade, axis=1)

            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['display_odds'],
                    text=df['msg'],
                    mode='lines+markers',
                    name=f'trade {i}',
                    **display_config.get('chart_args', {}),
                ),
                **display_config.get('trace_args', {}),
            )

    @staticmethod
    def set_figure_layout(fig: go.Figure, title: str, chart_start: datetime, chart_end: datetime):
        """set plotly figure layouts with a title, limit x axis from start time minus display seconds"""

        # set title
        fig.update_layout(title=title)

        # dont run if fig data is empty
        if not fig.data:
            return

        # verify trace
        def trace_verify(trace):
            return (
                    'y' in trace and
                    'yaxis' in trace and
                    trace['yaxis'] == 'y' and
                    len(trace['y']) and
                    general.constructor_verify(trace['y'][0], float)
            )

        # get primary yaxis maximum and minimum values by getting max/min of each trace
        y_min = min([
            min(trace['y'])
            for trace in fig.data
            if trace_verify(trace)
        ])
        y_max = max([
            max(trace['y'])
            for trace in fig.data
            if trace_verify(trace)
        ])

        # get index of minimum yaxis value, subtract 1 for display buffer
        i_min = closest_tick(y_min, return_index=True)
        i_min = max(0, i_min - 1)

        # get index of maximum yaxis value, add 1 for display buffer
        i_max = closest_tick(y_max, return_index=True)
        i_max = min(len(LTICKS_DECODED) - 1, i_max + 1)

        # remove range slider and set chart xaxis display limits
        fig.update_xaxes({
            'rangeslider': {
                'visible': False
            },
            'range': [
                chart_start,
                chart_end
            ],
        })

        # set primary yaxis gridlines to betfair ticks within range
        fig.update_yaxes({
            'tickmode': 'array',
            'tickvals': LTICKS_DECODED[i_min:i_max + 1],
        })

        # set secondary yaxis, manually set ticks to auto and number to display or for some reason they appear bunched up?
        fig.update_yaxes({
            'showgrid': False,
            'tickmode': 'auto',
            'nticks': 10,
        }, secondary_y=True)


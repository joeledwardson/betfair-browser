import os

from plotly.graph_objects import Figure
from os import path
from typing import List, Dict, Optional, TypedDict, Any
import pandas as pd
import logging
from datetime import datetime
import yaml
import json
from json.decoder import JSONDecodeError
import importlib
from flask_caching import Cache
import betfairlightweight
import queue
import sys
from betfairlightweight.resources.bettingresources import MarketBook

from myutils.betfair import BufferStream
import myutils.dictionaries
import myutils.files
import mytrading.exceptions
import mytrading.process
import myutils.datetime
from .config import MarketFilter
from .formatters import get_formatters
from ..exceptions import SessionException
from mytrading.utils import bettingdb as bdb, dbfilter as dbf
from mytrading.strategy import tradetracker, messages as msgs
from mytrading.strategy import feature as ftrutils
from mytrading import visual as figlib
from myutils import timing
import mybrowser


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class LoadedMarket(TypedDict):
    market_id: str
    info: Dict
    strategy_id: Optional[str]
    runners: Dict


def get_strat_filters(strat_sel_fmt):
    return [
        dbf.DBFilterMulti(
            'strategy_id',
            fmt_spec=strat_sel_fmt,
            order_col='exec_time',
            is_desc=True,
            cols=['strategy_id', 'exec_time', 'name']
        )
    ]


class Session:

    MODULES = ['myutils', 'mytrading']
    FTR_DEFAULT = {
        'ltp': {'name': 'RFLTP'},
        'best_back': {'name': 'RFBck'},
        'best_lay': {'name': 'RFLay'}
    }

    def get_yaml_files(self, dir_name: str, file_ext: str = '.yaml') -> Dict[str, Any]:
        """
        load yaml files from a directory
        from within the root project mybrowser, each yaml file mapped to file names
        e.g. directory with files "a.yaml" and "b.yaml" would return {"a": {...}, "b": {...}}
        """
        data = {}
        dir_path = path.join(mybrowser.__path__[0], dir_name)
        for filename in os.listdir(dir_path):
            name, ext = path.splitext(filename)
            if ext == file_ext:
                file_path = path.join(dir_path, filename)
                with open(file_path, 'r') as stream:
                    data[name] = yaml.safe_load(stream)
        return data

    def __init__(self, cache: Cache, config, market_filters: List[MarketFilter]):
        @cache.memoize(60)
        def get_market_records(market_id) -> List[List[MarketBook]]:
            print(f'**** reading market "{market_id}"')
            row = self.betting_db.read('marketstream', {'market_id': market_id})
            buffer = row['stream_updates']
            q = queue.Queue()
            listener = betfairlightweight.StreamListener(
                output_queue=q,
                max_latency=sys.float_info.max
            )
            streamer = BufferStream.generator(buffer, listener)
            streamer.start()
            return list(q.queue)

        self.get_market_records = get_market_records

        active_logger.info(f'configuration values:\n{yaml.dump(config, indent=4)}')
        active_logger.info(f'configuration end')

        self.config = config  # parsed configuration
        self.tbl_formatters = get_formatters(config)  # registrar of table formatters

        self._market_filters = dbf.DBFilterHandler([flt.filter for flt in market_filters])
        self._strategy_filters = dbf.DBFilterHandler(
            get_strat_filters(config['MARKET_FILTER']['strategy_sel_format'])
        )  # db strategy filters

        # betting database instance
        self._db_kwargs = {}
        if 'DB_CONFIG' in config:
            self._db_kwargs = config['DB_CONFIG']
        self.betting_db = bdb.BettingDB(**self._db_kwargs)

        self.feature_configs = dict()
        self.plot_configs = dict()
        self.update_configs()
        active_logger.info(f'found {len(self.feature_configs)} feature configurations')
        active_logger.info(f'found {len(self.plot_configs)} plot configurations')

    def update_configs(self):
        self.feature_configs = self.get_yaml_files('configurations_feature')
        self.plot_configs = self.get_yaml_files('configurations_plot')

    def serialise_loaded_market(self, mkt: LoadedMarket) -> None:
        self.betting_db.meta_serialise(mkt['info'])

    def deserialise_loaded_market(self, mkt: LoadedMarket) -> None:
        self.betting_db.meta_de_serialise(mkt['info'])
        # dash uses JSON strings for keys, have to convert back to integers for runner IDs
        mkt['runners'] = {int(k): v for k, v in mkt['runners'].items()}

    def market_filter_conditions(self, values: List[Any]):
        return self._market_filters.filters_conditions(self.betting_db._dbc.tables['marketmeta'], values)

    @classmethod
    def reload_modules(cls) -> int:
        """
        reload all modules within 'mytrading' or 'myutils'
        """
        n = 0
        for k in list(sys.modules.keys()):
            if any([m in k for m in cls.MODULES]):
                importlib.reload(sys.modules[k])
                active_logger.debug(f'reloaded library {k}')
                n += 1
        active_logger.info('libraries reloaded')
        return n

    def reload_database(self):
        """reload database instance"""
        self.betting_db.close()
        del self.betting_db
        self.betting_db = bdb.BettingDB(**self._db_kwargs)

    def get_plot_config(self, plt_key: str) -> Dict:
        """get plot configuration or empty dictionary from key"""
        plt_cfg = {}
        if plt_key:
            if plt_key in self.plot_configs:
                plt_cfg = self.plot_configs[plt_key]
            else:
                raise SessionException(f'selected plot configuration "{plt_key}" not in plot configurations')
        return plt_cfg

    def get_feature_config(self, ftr_key: str) -> Optional[Dict]:
        """
        get feature configuration dictionary - if no selection passed use default from configs
        return None on failure to retrieve configuration
        """
        if not ftr_key:
            return self.FTR_DEFAULT
        else:
            if ftr_key not in self.feature_configs:
                raise SessionException(f'selected feature config "{ftr_key}" not found in list')
            else:
                return self.feature_configs[ftr_key]

    def format_timings(self, summary: List[timing.TimingResult]) -> List[Dict]:
        """
        get list of dict values for Function, Count and Mean table values for function timings
        """
        tms = sorted(summary, key=lambda v: v['function'])
        tbl_cols = dict(self.config['TIMINGS_TABLE_COLS'])
        tms = [{
            k: v
            for k, v in t.items() if k in tbl_cols.keys()
        } for t in tms]
        timings_formatters = dict(self.config['TIMINGS_TABLE_FORMATTERS'])
        for row in tms:
            for col_id in row.keys():
                if col_id in timings_formatters.keys():
                    val = row[col_id]
                    formatter = self.tbl_formatters[timings_formatters[col_id]]
                    row[col_id] = formatter(val)
        return tms

    def market_load(self, market_id, strategy_id) -> LoadedMarket:
        record_list = self.get_market_records(market_id)
        if not len(record_list):
            raise SessionException(f'record list is empty')

        # rows are returned with additional "runner_profit" column
        rows = self.betting_db.rows_runners(market_id, strategy_id)
        self._apply_formatters(rows, dict(self.config['RUNNER_TABLE_FORMATTERS']))
        meta = self.betting_db.read_mkt_meta(market_id)

        start_odds = mytrading.process.get_starting_odds(record_list)
        drows = [dict(r) for r in rows]
        rinf = {
            r['runner_id']: r | {
                'starting_odds': start_odds.get(r['runner_id'], 999)
            }
            for r in drows
        }
        return LoadedMarket(
            market_id=market_id,
            info=dict(meta),
            strategy_id=strategy_id,
            runners=myutils.dictionaries.dict_sort(rinf, key=lambda item: item[1]['starting_odds'])
        )

    def _apply_formatters(self, tbl_rows: List[Dict], fmt_config: Dict):
        for i, row in enumerate(tbl_rows):
            # apply custom formatting to table row values
            for k, v in row.items():
                if k in fmt_config:
                    nm = fmt_config[k]
                    f = self.tbl_formatters[nm]
                    if v is not None:
                        row[k] = f(v)

    def mkt_tbl_rows(self, cte, order_col=None, order_asc=True):
        col_names = list(self.config['MARKET_TABLE_COLS'].keys()) + ['market_profit']
        max_rows = int(self.config['DB']['max_rows'])
        tbl_rows = self.betting_db.rows_market(cte, col_names, max_rows, order_col, order_asc)
        self._apply_formatters(tbl_rows, dict(self.config['MARKET_TABLE_FORMATTERS']))
        return tbl_rows

    def strats_tbl_rows(self):
        tbl_rows = self.betting_db.rows_strategy(self.config['TABLE']['strategy_rows'])
        self._apply_formatters(tbl_rows, dict(self.config['STRATEGY_TABLE_FORMATTERS']))
        return tbl_rows

    def read_orders(self, market_id: str, strategy_id: str, selection_id: int, start_time: datetime) -> pd.DataFrame:
        """
        get profit for each order from order updates file
        """
        buffer = self.get_strategy_updates(market_id, strategy_id)
        # get order results
        try:
            lines = [json.loads(ln) for ln in buffer.splitlines()]
        except JSONDecodeError as e:
            raise SessionException(f'error decoding orders buffer: {e}')

        # get order infos for each message close and check not blank
        lines = [
            ln['order_info'] for ln in lines if
            ln['msg_type'] == msgs.MessageTypes.MSG_MARKET_CLOSE.name and
            'order_info' in ln and ln['order_info'] and
            ln['order_info']['order_type']['order_type'] == 'Limit' and
            ln['selection_id'] == selection_id
        ]
        if not lines:
            return pd.DataFrame()

        df = pd.DataFrame([{
            'date': datetime.fromtimestamp(o['date_time_created']),
            'trade': o['trade']['id'],
            'side': o['info']['side'],
            'price': o['order_type']['price'],
            'size': o['order_type']['size'],
            'm-price': o['average_price_matched'],
            'matched': o['info']['size_matched'],
            'order-profit': tradetracker.TradeTracker.dict_order_profit(o)
        } for o in lines])

        # sum order profits in each trade
        df['trade-profit'] = df.groupby(['trade'])['order-profit'].transform('sum')

        # convert trade UUIDs to indexes for easy viewing
        trade_ids = list(df['trade'].unique())
        df['trade'] = [trade_ids.index(x) for x in df['trade'].values]
        df['t-start'] = [myutils.datetime.format_timedelta(start_time - dt) for dt in df['date']]

        currency_cols = [
            'trade-profit',
            'order-profit',
            'size',
            'matched',
        ]

        def currency_format(x):
            return f'£{x:.2f}' if x != 0 else ''
        for col in currency_cols:
            df[col] = df[col].apply(currency_format)

        # sort earliest first
        return df.sort_values(by=['date'])

    @staticmethod
    def fig_title(mkt_info: Dict, name: str, selection_id: int) -> str:
        """
        generate figure title from database market meta-information, runner name and runner selection ID
        """
        return '{} {} {} "{}", name: "{}", ID: "{}"'.format(
            mkt_info['event_name'],
            mkt_info['market_time'],
            mkt_info['market_type'],
            mkt_info['market_id'],
            name,
            selection_id
        )

    def get_strategy_updates(self, market_id, strategy_id) -> str:
        row = self.betting_db.read('strategyupdates', {
            'strategy_id': strategy_id,
            'market_id': market_id,
        })
        return row['strategy_updates']

    def fig_plot(
            self,
            market_info: LoadedMarket,
            selection_id,
            secs,
            ftr_key,
            plt_key
    ) -> (ftrutils.FeatureHolder, Figure):

        # if no active market selected then abort
        if not market_info:
            raise SessionException('no market information')
        market_records = self.get_market_records(market_info['market_id'])
        if not market_records:
            raise SessionException('no market records')

        # get name and title
        if selection_id not in market_info['runners']:
            raise SessionException(f'selection ID "{selection_id}" not found in market runners')
        name = market_info['runners'][selection_id]['runner_name'] or 'N/A'
        title = self.fig_title(market_info['info'], name, selection_id)
        active_logger.info(f'producing figure for runner {selection_id}, name: "{name}"')

        # get start/end of chart datetimes
        dt0 = market_records[0][0].publish_time
        mkt_dt = market_info['info']['market_time']
        start = figlib.FeatureFigure.get_chart_start(
            display_seconds=secs, market_time=mkt_dt, first=dt0
        )
        end = mkt_dt

        # get orders dataframe (or None)
        orders = None
        if market_info['strategy_id']:
            row = self.betting_db.read('strategyupdates', {
                'strategy_id': market_info['strategy_id'],
                'market_id': market_info['market_id'],
            })
            buffer = row['strategy_updates']

            # p = self.betting_db.path_strat_updates(market_info['market_id'], market_info['strategy_id'])
            # if not path.exists(p):
            #     raise SessionException(f'could not find cached strategy market file:\n-> "{p}"')

            try:
                orders = tradetracker.TradeTracker.get_orders_from_buffer(buffer)
            except mytrading.exceptions.TradeTrackerException as e:
                raise SessionException(e)
            if not orders.shape[0]:
                raise SessionException(f'could not find any rows in strategy updates')

            orders = orders[orders['selection_id'] == selection_id]
            offset_secs = float(self.config['PLOT_CONFIG']['order_offset_secs'])
            start = figlib.FeatureFigure.modify_start(start, orders, offset_secs)
            end = figlib.FeatureFigure.modify_end(end, orders, offset_secs)

        # feature and plot configurations
        plt_cfg = self.get_plot_config(plt_key)
        ftr_cfg = self.get_feature_config(ftr_key)

        # generate plot by simulating features
        features = ftrutils.FeatureHolder.generator(ftr_cfg)
        data = features.simulate(
            hist_records=market_records,
            selection_id=selection_id,
            cmp_start=start,
            cmp_end=end,
            buffer_s=float(self.config['PLOT_CONFIG']['cmp_buffer_secs'])
        )

        # generate figure and display
        fig = figlib.FeatureFigure(
            ftrs_data=data,
            plot_cfg=plt_cfg,
            title=title,
            chart_start=start,
            chart_end=end,
            orders_df=orders
        )
        return features, fig.fig

    @property
    def filters_mkt(self):
        return self._market_filters

    @property
    def filters_strat(self):
        return self._strategy_filters


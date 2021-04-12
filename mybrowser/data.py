from functools import partial
from betfairlightweight.resources.bettingresources import MarketBook
from os import path
from typing import List, Dict, Union, Optional
import pandas as pd
import logging
from sqlalchemy.exc import SQLAlchemyError
import importlib
import sys
from datetime import datetime


from mytrading.visual import profits
from mytrading.tradetracker.messages import MessageTypes
from mytrading.utils import security as mysecurity
from mytrading.utils.bettingdb import BettingDB
from mytrading.tradetracker import orderinfo
from mytrading.process import prices
from myutils import mypath, mytiming, jsonfile, generic


from . import bfcache
from .db import table as dbtable


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def get_ftr_configs(config_dir: str) -> Dict:
    """
    get dictionary of configuration file name (without ext) to dict from dir

    Parameters
    ----------
    info_strings :
    config_dir :

    Returns
    -------

    """

    # check directory is set
    if type(config_dir) is not str:
        active_logger.error('directory not set')
        return dict()

    # check actually exists
    if not path.exists(config_dir):
        active_logger.error(f'directory does not exist!')
        return dict()

    # dict of configs to return
    configs = dict()

    # get files in directory
    _, _, files = mypath.walk_first(config_dir)

    # loop files
    for file_name in files:

        # get file path and name without ext
        file_path = path.join(config_dir, file_name)
        name, _ = path.splitext(file_name)

        # read configuration from dictionary
        cfg = jsonfile.read_file_data(file_path)

        # check config successfully parsed
        if cfg is not None:
            configs[name] = cfg

    active_logger.info(f'{len(configs)} valid configuration files found from {len(files)} files')
    active_logger.info(f'feature configs: {list(configs.keys())}')
    return configs


# TODO - how to remove globals to make this multiprocess valid? strategy id, runner names, market info, start odds
#  could all be cached or stored in hidden divs.
# TODO - logger for each session?
class Session:

    def init_db(self, **db_kwargs):
        self.betting_db = BettingDB(**db_kwargs)

    def init_config(self, config):
        self.config = config

    def __init__(self):

        self.config: Optional[Dict] = None

        # market info - selected strategy, runner names, market meta dict, and streaming update list
        self.strategy_id = None
        self.runner_names = {}
        self.db_mkt_info = {}
        self.start_odds: Dict[int, float] = {} # dict of {selection ID: starting odds} of runners in active market
        self.record_list: List[List[MarketBook]] = []
        self.runner_infos = []  # TODO - factor names, start odds and runner infos into single dict

        # betting database instance
        self.betting_db: Optional[BettingDB] = None

        # API client instance
        self.trading = mysecurity.get_api_client()

        # dictionary holding of {file name: config} for feature/plot configurations
        self.feature_configs = dict()
        self.plot_configs = dict()

    def load_market(self, market_id, strategy_id) -> bool:

        # check strategy valid if one is selected, when writing info to cache
        if strategy_id:
            if not bfcache.w_strat(strategy_id, market_id, self.betting_db):
                return False

        # check market stream is valid when writing to cache
        if not bfcache.w_mkt(market_id, self.betting_db):
            return False

        # read market stream back from cache and check valid
        p = bfcache.p_mkt(market_id)
        record_list = bfcache.r_mkt(p, self.trading)
        if not record_list:
            return False

        # get runner name/profit and market metadata from db
        try:
            rows = dbtable.runner_rows(self.betting_db, market_id, strategy_id)
            meta = dbtable.market_meta(self.betting_db, market_id)
        except SQLAlchemyError as e:
            active_logger.warning(f'failed getting runners rows/market meta from DB: {e}', exc_info=True)
            return False

        # put market information into self
        self.strategy_id = strategy_id
        self.record_list = record_list
        self.db_mkt_info = dict(meta)
        self.start_odds = generic.dict_sort(prices.starting_odds(record_list))
        self.runner_names = {
            dict(r)['runner_id']: dict(r)['runner_name']
            for r in rows
        }
        self.runner_infos = [dict(r) for r in rows]

        return True

    def clear_market(self):
        self.runner_names = {}
        self.db_mkt_info = {}
        self.start_odds = {}
        self.record_list = []
        self.strategy_id = None
        self.runner_infos = []

    def load_ftr_configs(self):

        # get feature configs
        feature_dir = path.abspath(self.config['CONFIG_PATHS']['feature'])
        active_logger.info(f'getting feature configurations from:\n-> {feature_dir}"')
        self.feature_configs = get_ftr_configs(feature_dir)

        # get plot configurations
        plot_dir = path.abspath(self.config['CONFIG_PATHS']['feature'])
        active_logger.info(f'getting plot configurations from:\n-> {plot_dir}"')
        self.plot_configs = get_ftr_configs(plot_dir)

    def get_plot_config(self, plt_key: str) -> Dict:
        """
        get plot configuration or empty dictionary
        """
        plt_cfg = {}
        if plt_key:
            if plt_key in self.plot_configs:
                active_logger.info(f'using selected plot configuration "{plt_key}"')
                plt_cfg = self.plot_configs[plt_key]
            else:
                active_logger.warning(f'selected plot configuration "{plt_key}" not in plot configurations')
        else:
            active_logger.info('no plot configuration selected')
        return plt_cfg

    def get_timings(self) -> List[Dict]:
        """
        get list of dict values for Function, Count and Mean table values for function timings
        """
        tms = mytiming.get_timings_summary()
        if not tms:
            active_logger.warning('no timings on which to produce table')
            return list()
        tms = sorted(tms, key=lambda v: v['Mean'], reverse=True)
        td_fmt = self.config['TIMING_CONFIG']['str_format']
        f = partial(mytiming.format_timedelta, fmt=td_fmt)
        tms = [{
            k: f(v) if k == 'Mean' else v
            for k, v in t.items() if k in ['Function', 'Count', 'Mean']
        } for t in tms]
        return tms

    def get_orders(self) -> Union[pd.DataFrame, None]:
        """
        get dataframe of order updates (datetime set as index), empty dataframe if strategy not specified,
        None if strategy specified by fail
        """

        if self.strategy_id:
            p = bfcache.p_strat(self.strategy_id, self.db_mkt_info['market_id'])
            if not path.exists(p):
                active_logger.warning(f'could not find cached strategy market file:\n-> "{p}"')
                return None

            orders = orderinfo.get_order_updates(p)
            if not orders.shape[0]:
                active_logger.warning(f'could not find any rows in cached strategy market file:\n-> "{p}"')
                return None

            active_logger.info(f'loaded {orders.shape[0]} rows from cached strategy market file\n-> "{p}"')
            return orders
        else:
            return pd.DataFrame()

    @staticmethod
    def reload_modules():
        """
        reload all modules within 'mytrading' or 'myutils'
        """
        for k in list(sys.modules.keys()):
            if 'mytrading' in k or 'myutils' in k:
                importlib.reload(sys.modules[k])
                active_logger.debug(f'reloaded library {k}')
        active_logger.info('libraries reloaded')

    @staticmethod
    def _read_profits(p, selection_id) -> Optional[pd.DataFrame]:
        """
        get profit for each order from order updates file
        """

        # get order results
        lines = jsonfile.read_file_lines(p)

        # get order infos and check not blank
        lines = [
            ln['order_info'] for ln in lines if
            ln['msg_type'] == MessageTypes.MSG_MARKET_CLOSE.name and
            'order_info' in ln and ln['order_info'] and
            ln['order_info']['order_type']['order_type'] == 'Limit' and
            ln['selection_id'] == selection_id
        ]
        if not lines:
            return pd.DataFrame()

        # lines = [order for order in lines if order['order_type']['order_type'] == 'Limit']

        attrs = {
            'date': 'date_time_created',
            'trade': 'trade.id',
            'side': 'info.side',
            'price': 'order_type.price',
            'size': 'order_type.size',
            'm-price': 'average_price_matched',
            'matched': 'info.size_matched'
        }

        df = pd.DataFrame([
            {
                k: generic.dgetattr(o, v, is_dict=True)
                for k, v in attrs.items()
            } for o in lines
        ])
        df['date'] = df['date'].apply(datetime.fromtimestamp)
        df['order £'] = [orderinfo.dict_order_profit(order) for order in lines]
        return df

    # TODO - strategy updates read at market load so dont have to do it for every call?
    def get_profits(self, selection_id) -> Optional[pd.DataFrame]:

        p = bfcache.p_strat(self.strategy_id, self.db_mkt_info['market_id'])
        active_logger.info(f'reading strategy market cache file:\n-> {p}')
        if not path.isfile(p):
            active_logger.warning(f'file does not exist')
            return None

        df = self._read_profits(p, selection_id)
        if not df.shape[0]:
            active_logger.warning(f'Retrieved profits dataframe is empty')
            return None

        return profits.process_profit_table(df, self.db_mkt_info['market_time'])

    def log_records_info(self):
        """
        log information about records
        """
        rl = self.record_list
        mt = self.db_mkt_info['market_time']

        active_logger.info(f'{mt}, market time')
        active_logger.info(f'{rl[0][0].publish_time}, first record timestamp')
        active_logger.info(f'{rl[-1][0].publish_time}, final record timestamp')
        for r in rl:
            if r[0].market_definition.in_play:
                active_logger.info(f'{r[0].publish_time}, first inplay')
                break
        else:
            active_logger.info(f'no inplay elements found')
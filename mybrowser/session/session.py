from functools import partial
from betfairlightweight.resources.bettingresources import MarketBook
from os import path
import os
from typing import List, Dict, Optional
import pandas as pd
import logging
import sys
from datetime import datetime
from configparser import ConfigParser
import yaml
import json
from json.decoder import JSONDecodeError
import importlib.resources as pkg_resources
import importlib


import mytrading.exceptions
import mytrading.process
from mytrading.strategy import messages as msgs
from mytrading import utils as trutils
from mytrading.utils import bettingdb as bdb, dbfilter as dbf
from mytrading.strategy import tradetracker
from mytrading import visual as figlib
from mytrading.strategy import feature as ftrutils
from mytrading import configs as cfgs
from myutils import mytiming, mygeneric
from myutils import myregistrar as myreg

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class SessionException(Exception):
    pass


def get_mkt_filters(mkt_dt_fmt):
    return [
        dbf.DBFilterJoin(
            "sport_id",
            join_tbl_name='sportids',
            join_id_col='sport_id',
            join_name_col='sport_name'
        ),
        dbf.DBFilter(
            "market_type",
        ),
        dbf.DBFilter(
            "betting_type",
        ),
        dbf.DBFilter(
            'format',
        ),
        dbf.DBFilterJoin(
            "country_code",
            join_tbl_name='countrycodes',
            join_id_col='alpha_2_code',
            join_name_col='name'
        ),
        dbf.DBFilter(
            "venue",
        ),
        dbf.DBFilterDate(
            "market_time",
            mkt_dt_fmt
        ),
        dbf.DBFilterText(
            'market_id',
        )
    ]


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


def get_formatters(dt_format) -> myreg.MyRegistrar:
    formatters = myreg.MyRegistrar()

    @formatters.register_element
    def format_datetime(dt: datetime):
        return dt.strftime(dt_format)

    return formatters


# TODO - add strategy configuration loader and operator
class Session:

    MODULES = ['myutils', 'mytrading']
    CFG_LOCAL_FILE = 'config.txt'
    FTR_DEFAULT = {
        'ltp': {'name': 'RFLTP'},
        'best_back': {'name': 'RFBck'},
        'best_lay': {'name': 'RFLay'}
    }

    def __init__(self, config: Optional[ConfigParser] = None):

        # load configuration from local file if not passed, then print values
        if config is None:
            config = self.cfg_local()
        active_logger.info(f'configuration values:')
        for section in config.sections():
            active_logger.info(f'Section {section}, values:')
            for k, v in config[section].items():
                active_logger.info(f'{k}: {v}')
        active_logger.info(f'configuration end')

        self.config: ConfigParser = config  # parsed configuration
        self.tbl_formatters = get_formatters(config['FORMATTERS_CONFIG']['dt_format'])  # registrar of table formatters
        self.api_handler = trutils.APIHandler()   # API client instance

        self._flts_mkt = dbf.DBFilterHandler(
            get_mkt_filters(config['MARKET_FILTER']['mkt_date_format'])
        )  # db market filters
        self._flts_strat = dbf.DBFilterHandler(
            get_strat_filters(config['MARKET_FILTER']['strategy_sel_format'])
        )  # db strategy filters

        self.log_nwarn = 0  # number of logger warnings
        self.log_elements = list()  # logging elements

        # selected market info
        self.mkt_sid = None  # strategy ID
        self.mkt_info = {}  # database meta information dict
        self.mkt_records: List[List[MarketBook]] = []  # record list
        self.mkt_rnrs: Dict[int, Dict] = {}  # market runners information, indexed by runner ID

        # betting database instance
        self._db_kwargs = {}
        if config.has_section('DB_CONFIG'):
            self._db_kwargs = config['DB_CONFIG']
        self.betting_db = bdb.BettingDB(**self._db_kwargs)

        # feature-plot configurations
        self.ftr_fcfgs = dict()  # feature configurations
        self.ftr_pcfgs = dict()  # plot configurations

    @classmethod
    def cfg_local(cls):
        active_logger.info(f'reading configuration from default "{cls.CFG_LOCAL_FILE}"...')
        config = ConfigParser()
        txt = pkg_resources.read_text("mybrowser.session", cls.CFG_LOCAL_FILE)
        config.read_string(txt)
        return config

    @classmethod
    def rl_mods(cls):
        """
        reload all modules within 'mytrading' or 'myutils'
        """
        for k in list(sys.modules.keys()):
            if any([m in k for m in cls.MODULES]):
                importlib.reload(sys.modules[k])
                active_logger.debug(f'reloaded library {k}')
        active_logger.info('libraries reloaded')

    def rl_db(self):
        """reload database instance"""
        self.betting_db.close()
        del self.betting_db
        self.betting_db = bdb.BettingDB(**self._db_kwargs)

    @staticmethod
    def ftr_readf(config_dir: str) -> Dict:
        """get dictionary of (configuration file name without ext => config dict) directory of yaml files"""

        # check directory is set
        if type(config_dir) is not str:
            raise SessionException(f'directory "{config_dir}" is not a string')

        # check actually exists
        if not path.isdir(config_dir):
            raise SessionException(f'directory "{config_dir}" does not exist!')

        # dict of configs to return
        configs = dict()

        # get files in directory
        _, _, files = next(os.walk(config_dir))

        # loop files
        for file_name in files:

            # get file path and name without ext
            file_path = path.join(config_dir, file_name)
            name, ext = path.splitext(file_name)
            if ext != '.yaml':
                continue

            with open(file_path) as f:
                # The FullLoader parameter handles the conversion from YAML
                # scalar values to Python the dictionary format
                cfg = yaml.load(f, Loader=yaml.FullLoader)

            # check config successfully parsed
            if cfg is not None:
                configs[name] = cfg

        active_logger.info(f'{len(configs)} valid configuration files found from {len(files)} files')
        active_logger.info(f'feature configs: {list(configs.keys())}')
        return configs

    def ftr_update(self):
        """
        load feature and plot configurations from directory to dicts
        """
        # regenerate feature/plot configs (do at runtime so can reload lib)
        importlib.reload(cfgs)
        cfgs.ConfigGenerator(
            self.config['CONFIG_PATHS']['feature_src'],
            self.config['CONFIG_PATHS']['feature_out'],
            cfgs.reg_features
        ).reload()
        cfgs.ConfigGenerator(
            self.config['CONFIG_PATHS']['plot_src'],
            self.config['CONFIG_PATHS']['plot_out'],
            cfgs.reg_plots
        ).reload()

        # get feature configs
        feature_dir = path.abspath(path.expandvars(self.config['CONFIG_PATHS']['feature_out']))
        active_logger.info(f'getting feature configurations from:\n-> {feature_dir}"')
        self.ftr_fcfgs = self.ftr_readf(feature_dir)

        # get plot configurations
        plot_dir = path.abspath(path.expandvars(self.config['CONFIG_PATHS']['plot_out']))
        active_logger.info(f'getting plot configurations from:\n-> {plot_dir}"')
        self.ftr_pcfgs = self.ftr_readf(plot_dir)

    def ftr_pcfg(self, plt_key: str) -> Dict:
        """get plot configuration or empty dictionary from key"""
        plt_cfg = {}
        if plt_key:
            if plt_key in self.ftr_pcfgs:
                active_logger.info(f'using selected plot configuration "{plt_key}"')
                plt_cfg = self.ftr_pcfgs[plt_key]
            else:
                raise SessionException(f'selected plot configuration "{plt_key}" not in plot configurations')
        else:
            active_logger.info('no plot configuration selected')
        return plt_cfg

    def ftr_fcfg(self, ftr_key: str) -> Optional[Dict]:
        """
        get feature configuration dictionary - if no selection passed use default from configs
        return None on failure to retrieve configuration
        """

        if not ftr_key:
            active_logger.info(f'no feature config selected, using default "{self.FTR_DEFAULT}"')
            return self.FTR_DEFAULT
        else:
            if ftr_key not in self.ftr_fcfgs:
                raise SessionException(f'selected feature config "{ftr_key}" not found in list')
            else:
                active_logger.info(f'using selected feature config "{ftr_key}"')
                return self.ftr_fcfgs[ftr_key]

    def ftr_clear(self):
        """clear existing feature/plot configurations"""
        self.ftr_fcfgs = dict()
        self.ftr_pcfgs = dict()

    def tms_get(self) -> List[Dict]:
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

    def tms_clr(self):
        """
        clear timings registry
        """
        mytiming.clear_timing_register()

    def mkt_load(self, market_id, strategy_id):

        # check strategy valid if one is selected, when writing info to cache
        if strategy_id:
            self.betting_db.cache_strat_updates(strategy_id, market_id)
            self.betting_db.cache_strat_meta(strategy_id)

        self.betting_db.cache_mkt_stream(market_id)
        p = self.betting_db.path_mkt_updates(market_id)
        q = self.api_handler.get_historical(p)
        record_list = list(q.queue)
        if not len(record_list):
            raise SessionException(f'record list is empty')

        rows = self.betting_db.rows_runners(market_id, strategy_id)
        meta = self.betting_db.read_mkt_meta(market_id)

        start_odds = mytrading.process.get_starting_odds(record_list)
        drows = [dict(r) for r in rows]
        rinf = {
            r['runner_id']: r | {
                'start_odds': start_odds.get(r['runner_id'], 999)
            }
            for r in drows
        }

        # put market information into self
        self.mkt_sid = strategy_id
        self.mkt_records = record_list
        self.mkt_info = dict(meta)
        self.mkt_rnrs = mygeneric.dict_sort(rinf, key=lambda item:item[1]['start_odds'])

    def mkt_clr(self):
        self.mkt_info = {}
        self.mkt_records = []
        self.mkt_sid = None
        self.mkt_rnrs = {}

    def mkt_lginf(self):
        """
        log information about records
        """
        rl = self.mkt_records
        mt = self.mkt_info['market_time']

        active_logger.info(f'loaded market "{self.mkt_info["market_id"]}"')
        active_logger.info(f'{mt}, market time')
        active_logger.info(f'{rl[0][0].publish_time}, first record timestamp')
        active_logger.info(f'{rl[-1][0].publish_time}, final record timestamp')
        for r in rl:
            if r[0].market_definition.in_play:
                active_logger.info(f'{r[0].publish_time}, first inplay')
                break
        else:
            active_logger.info(f'no inplay elements found')

    @staticmethod
    def odr_rd(p, selection_id, mkt_dt) -> Optional[pd.DataFrame]:
        """
        get profit for each order from order updates file
        """

        # get order results
        try:
            with open(p) as f:
                lines = [json.loads(ln) for ln in f.readlines()]
        except JSONDecodeError as e:
            raise SessionException(f'error reading orders file "{p}": {e}')

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
        df['t-start'] = [mytiming.format_timedelta(mkt_dt - dt) for dt in df['date']]

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

    def odr_prft(self, selection_id) -> pd.DataFrame:
        p = self.betting_db.path_strat_updates(self.mkt_info['market_id'], self.mkt_sid)
        active_logger.info(f'reading strategy market cache file:\n-> {p}')
        if not path.isfile(p):
            raise SessionException(f'order file does not exist')

        df = self.odr_rd(p, selection_id, self.mkt_info['market_time'])
        if not df.shape[0]:
            raise SessionException(f'Retrieved profits dataframe is empty')

        return df

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

    def fig_plot(self, selection_id, secs, ftr_key, plt_key):

        # if no active market selected then abort
        if not self.mkt_records or not self.mkt_info:
            raise SessionException('no market information/records')

        # get name and title
        if selection_id not in self.mkt_rnrs:
            raise SessionException(f'selection ID "{selection_id}" not found in market runners')
        name = self.mkt_rnrs[selection_id]['runner_name'] or 'N/A'
        title = self.fig_title(self.mkt_info, name, selection_id)
        active_logger.info(f'producing figure for runner {selection_id}, name: "{name}"')

        # get start/end of chart datetimes
        dt0 = self.mkt_records[0][0].publish_time
        mkt_dt = self.mkt_info['market_time']
        start = figlib.FeatureFigure.get_chart_start(
            display_seconds=secs, market_time=mkt_dt, first=dt0
        )
        end = mkt_dt

        # get orders dataframe (or None)
        orders = None
        if self.mkt_sid:
            p = self.betting_db.path_strat_updates(self.mkt_info['market_id'], self.mkt_sid)
            if not path.exists(p):
                raise SessionException(f'could not find cached strategy market file:\n-> "{p}"')

            try:
                orders = tradetracker.TradeTracker.get_order_updates(p)
            except mytrading.exceptions.TradeTrackerException as e:
                raise SessionException(e)
            if not orders.shape[0]:
                raise SessionException(f'could not find any rows in cached strategy market file:\n-> "{p}"')

            orders = orders[orders['selection_id'] == selection_id]
            offset_secs = float(self.config['PLOT_CONFIG']['order_offset_secs'])
            start = figlib.FeatureFigure.modify_start(start, orders, offset_secs)
            end = figlib.FeatureFigure.modify_end(end, orders, offset_secs)
            active_logger.info(f'loaded {orders.shape[0]} rows from cached strategy market file\n-> "{p}"')

        # feature and plot configurations
        plt_cfg = self.ftr_pcfg(plt_key)
        ftr_cfg = self.ftr_fcfg(ftr_key)

        # generate plot by simulating features
        ftrs_data = ftrutils.FeatureHolder.gen_ftrs(ftr_cfg).sim_mktftrs(
            hist_records=self.mkt_records,
            selection_id=selection_id,
            cmp_start=start,
            cmp_end=end,
            buffer_s=float(self.config['PLOT_CONFIG']['cmp_buffer_secs'])
        )

        # generate figure and display
        fig = figlib.FeatureFigure(
            ftrs_data=ftrs_data,
            plot_cfg=plt_cfg,
            title=title,
            chart_start=start,
            chart_end=end,
            orders_df=orders
        )
        fig.show()

    @property
    def filters_mkt(self):
        return self._flts_mkt

    @property
    def filters_strat(self):
        return self._flts_strat

    def filters_mkt_tbl(self, cte):
        col_names = list(self.config['TABLE_COLS'].keys()) + ['market_profit']
        max_rows = int(self.config['DB']['max_rows'])
        fmt_config = self.config['TABLE_FORMATTERS']
        tbl_rows = self.betting_db.rows_market(cte, col_names, max_rows)
        for i, row in enumerate(tbl_rows):
            # apply custom formatting to table row values
            for k, v in row.items():
                if k in fmt_config:
                    nm = fmt_config[k]
                    f = self.tbl_formatters[nm]
                    row[k] = f(v)
        return tbl_rows


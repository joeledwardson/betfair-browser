from functools import partial
from betfairlightweight.resources.bettingresources import MarketBook
from os import path
from typing import List, Dict, Optional
import pandas as pd
import logging
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.functions import sum as sql_sum
import sqlalchemy
import importlib
import sys
from datetime import datetime
from configparser import ConfigParser
import yaml
import importlib.resources as pkg_resources

from mytrading.strategy import messages as msgs
from mytrading import utils as trutils
from mytrading.utils import bfcache
from mytrading.utils import bettingdb as bdb
from mytrading.strategy import tradetracker
from mytrading.process import prices
from mytrading import visual as figlib
from mytrading.strategy import feature as ftrutils
from myutils import mypath, mytiming, jsonfile, generic


from mybrowser.session import dbutils as dbtable
from mybrowser.session.dbfilters import DBFilters, DBFilter
from myutils.myregistrar import MyRegistrar

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class SessionException(Exception):
    pass


# TODO - this is poor
def get_formatters(config) -> MyRegistrar:
    formatters = MyRegistrar()

    @formatters.register_element
    def format_datetime(dt: datetime):
        return dt.strftime(config['FORMATTERS_CONFIG']['dt_format'])

    return formatters


class Session:

    MODULES = ['myutils', 'mytrading']
    CFG_LOCAL_FILE = 'config.txt'

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
        self.tbl_formatters = get_formatters(config)  # registrar of table formatters
        self.cache_rt = config['CONFIG_PATHS']['cache']  # cache root dir
        self.trading = trutils.BFSecurity().API_client  # API client instance
        self.db_filters = DBFilters(
            config['MARKET_FILTER']['mkt_date_format'],
            config['MARKET_FILTER']['strategy_sel_format']
        )  # market database filters

        self.log_nwarn = 0  # number of logger warnings
        self.log_elements = list()  # logging elements

        # selected market info
        self.mkt_sid = None  # strategy ID
        self.mkt_info = {}  # database meta information dict
        self.mkt_records: List[List[MarketBook]] = []  # record list
        self.mkt_rnrs: Dict[int, Dict] = {}  # market runners information, indexed by runner ID

        # betting database instance
        db_kwargs = {}
        if config.has_section('DB_CONFIG'):
            db_kwargs = config['DB_CONFIG']
        self.betting_db = bdb.BettingDB(**db_kwargs)

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

    @staticmethod
    def ftr_readf(config_dir: str) -> Dict:
        """get dictionary of (configuration file name without ext => config dict) directory of yaml files"""

        # check directory is set
        if type(config_dir) is not str:
            raise SessionException(f'directory "{config_dir}" is not a string')

        # check actually exists
        if not path.exists(config_dir):
            raise SessionException(f'directory "{config_dir}" does not exist!')

        # dict of configs to return
        configs = dict()

        # get files in directory
        _, _, files = mypath.walk_first(config_dir)

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
        # get feature configs
        feature_dir = path.abspath(self.config['CONFIG_PATHS']['feature'])
        active_logger.info(f'getting feature configurations from:\n-> {feature_dir}"')
        self.ftr_fcfgs = self.ftr_readf(feature_dir)

        # get plot configurations
        plot_dir = path.abspath(self.config['CONFIG_PATHS']['plot'])
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

        dft = self.config['PLOT_CONFIG']['default_features']
        if not ftr_key:
            cfg_key = dft
            active_logger.info(f'no feature config selected, using default "{dft}"')
        else:
            if ftr_key not in self.ftr_fcfgs:
                raise SessionException(f'selected feature config "{ftr_key}" not found in list')
            else:
                active_logger.info(f'using selected feature config "{ftr_key}"')
                cfg_key = ftr_key
        return self.ftr_fcfgs.get(cfg_key)

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

    def mkt_load(self, market_id, strategy_id) -> bool:

        # check strategy valid if one is selected, when writing info to cache
        if strategy_id:
            if not bfcache.w_strat(strategy_id, market_id, self.betting_db, self.cache_rt):
                return False

        # check market stream is valid when writing to cache
        if not bfcache.w_mkt(market_id, self.betting_db, self.cache_rt):
            return False

        # read market stream back from cache and check valid
        p = bfcache.p_mkt(market_id, self.cache_rt)
        record_list = bfcache.r_mkt(p, self.trading)
        if not record_list:
            return False

        # get runner name/profit and market metadata from session
        try:
            rows = dbtable.runner_rows(self.betting_db, market_id, strategy_id)
            meta = dbtable.market_meta(self.betting_db, market_id)
        except SQLAlchemyError as e:
            active_logger.warning(f'failed getting runners rows/market meta from DB: {e}', exc_info=True)
            return False

        start_odds = prices.starting_odds(record_list)
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
        self.mkt_rnrs = generic.dict_sort(rinf, key=lambda item:item[1]['start_odds'])

        return True

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
        lines = jsonfile.read_file_lines(p)

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

        p = bfcache.p_strat(self.mkt_sid, self.mkt_info['market_id'], self.cache_rt)
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

        # TODO - exit if selection iD not in runners info
        # get name and title
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
            p = bfcache.p_strat(self.mkt_sid, self.mkt_info['market_id'], self.cache_rt)
            if not path.exists(p):
                raise SessionException(f'could not find cached strategy market file:\n-> "{p}"')

            try:
                orders = tradetracker.TradeTracker.get_order_updates(p)
            except tradetracker.TrackerException as e:
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

    def flt_upmkt(self, clear, *flt_args):
        """
        update database market filters
        """
        self.db_filters.update_filters('MARKETFILTERS', clear, *flt_args)

    def flt_upsrt(self, clear, *flt_args):
        """
        update database strategy filters
        """
        self.db_filters.update_filters('STRATEGYFILTERS', clear, *flt_args)

    def flt_valsmkt(self):
        """
        database market filters values
        """
        return self.db_filters.filters_values('MARKETFILTERS')

    def flt_optsmkt(self, cte):
        """
        database market filters options
        """
        return self.db_filters.filters_labels('MARKETFILTERS', self.betting_db, cte)

    def flt_valssrt(self):
        """
        database strategy filters values
        """
        return self.db_filters.filters_values('STRATEGYFILTERS')

    def flt_optssrt(self, cte):
        """
        database strategy filters options
        """
        return self.db_filters.filters_labels('STRATEGYFILTERS', self.betting_db, cte)

    def flt_ctemkt(self, strategy_id):
        """
        get filtered database market common table expression (CTE)
        """

        db = self.betting_db
        meta = self.betting_db.tables['marketmeta']
        sr = db.tables['strategyrunners']

        # TODO - add error checking for sqlalchemy
        if strategy_id:
            strat_cte = db.session.query(
                sr.columns['market_id'],
                sql_sum(sr.columns['profit']).label('market_profit')
            ).filter(
                sr.columns['strategy_id'] == strategy_id
            ).group_by(
                sr.columns['market_id']
            ).cte()

            q = db.session.query(
                meta,
                strat_cte.c['market_profit']
            ).join(
                strat_cte,
                meta.columns['market_id'] == strat_cte.c['market_id']
            )
        else:
            q = self.betting_db.session.query(
                meta,
                sqlalchemy.null().label('market_profit')
            )

        conditions = [
            f.db_filter(meta)
            for f in DBFilter.reg['MARKETFILTERS'] if f.value
        ]
        q = q.filter(*conditions)
        return q.cte()

    def flt_ctesrt(self):
        """
        get filtered database strategy common table expression (CTE)
        """
        db = self.betting_db
        meta = db.tables['strategymeta']
        conditions = [
            f.db_filter(meta)
            for f in DBFilter.reg['STRATEGYFILTERS'] if f.value
        ]
        q = db.session.query(meta).filter(*conditions)
        return q.cte()

    def flt_tbl(self, cte):

        col_names = list(self.config['TABLE_COLS'].keys()) + ['market_profit']
        cols = [cte.c[nm] for nm in col_names]

        fmt_config = self.config['TABLE_FORMATTERS']
        max_rows = int(self.config['DB']['max_rows'])
        q_final = self.betting_db.session.query(*cols).limit(max_rows)
        q_result = q_final.all()
        tbl_rows = [dict(r) for r in q_result]
        for i, row in enumerate(tbl_rows):

            # apply custom formatting to table row values
            for k, v in row.items():
                if k in fmt_config:
                    nm = fmt_config[k]
                    f = self.tbl_formatters[nm]
                    row[k] = f(v)
        return tbl_rows


from __future__ import annotations
import betfairlightweight
from betfairlightweight.resources.streamingresources import MarketDefinition
from betfairlightweight.resources.bettingresources import MarketCatalogue, MarketBook
from betfairlightweight.streaming.listener import StreamListener
from betfairlightweight import APIClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Table
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.dialects.postgresql import base as psqlbase
from sqlalchemy.dialects.postgresql import json as psqljson
from queue import Queue
import logging
from typing import Optional, Dict, List, Callable
import keyring
from os import path
import os
from datetime import datetime, timedelta
import zlib
import yaml
import json
import sys
from myutils.myregistrar import MyRegistrar
from ..exceptions import DBException
from ..strategy.tradetracker import TradeTracker
from ..strategy.messages import MessageTypes

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

db_processors = MyRegistrar()


@db_processors.register_element
def prc_compress(data):
    return zlib.compress(data)


@db_processors.register_element
def prc_decompress(data):
    return zlib.decompress(data)


@db_processors.register_element
def prc_str_encode(data):
    return data.encode()


@db_processors.register_element
def prc_str_decode(data):
    return data.decode()


@db_processors.register_element
def prc_td_to_float(data: timedelta):
    return data.total_seconds()


@db_processors.register_element
def prc_td_from_float(data):
    return timedelta(seconds=data)


@db_processors.register_element
def prc_dt_from_str(data):
    return datetime.fromisoformat(data)


@db_processors.register_element
def prc_dt_to_str(data):
    return data.isoformat()


@db_processors.register_element
def prc_json_encode(data):
    return json.dumps(data)


@db_processors.register_element
def prc_json_decode(data):
    return json.loads(data)


class DBBase:
    def __init__(
            self,
            db_lang,
            db_user,
            db_host,
            db_port,
            db_name,
            db_pwd,
            db_engine=None,
            col_processors=None
    ):
        self.col_prcs = col_processors or dict()
        engine_str = f'+{db_engine}' if db_engine else ''
        self.Base = automap_base()
        self.engine = create_engine(
            f'{db_lang}{engine_str}://{db_user}:{db_pwd}'
            f'@{db_host}:{db_port}/{db_name}'
        )
        self.Base.prepare(self.engine, reflect=True)
        self.session = Session(self.engine)
        self.tables: Dict[str, Table] = self.Base.metadata.tables

    def _validate_tbl(self, tbl_name: str):
        if tbl_name not in self.tables:
            raise DBException(f'error inserting row, table "{tbl_name}" not found in tables')
        if tbl_name not in self.Base.classes:
            raise DBException(f'error inserting row, table "{tbl_name}" not found in base')

    def _validate_cols(self, tbl_name: str, cols: List[str]):
        for col in cols:
            if col not in self.tables[tbl_name].columns:
                raise DBException(f'column "{col}" not found in table "{tbl_name}"')

    def _validate_pkeys(self, tbl_nm: str, pkey_flts: Dict):
        tbl_pkeys = tuple(x.name for x in self.tables[tbl_nm].primary_key)
        flt_pkeys = tuple(pkey_flts.keys())
        if tbl_pkeys != flt_pkeys:
            raise DBException(
                f'error writing cache, table primary keys "{tbl_pkeys}" does not match specified "{flt_pkeys}"'
            )

    def row_exist(self, tbl_nm: str, pkey_flts: Dict) -> bool:
        """
        Determine if row(s) exist in database for a given table
        """
        return self.session.query(self.tables[tbl_nm]).filter(
            *[self.tables[tbl_nm].columns[k] == v for k, v in pkey_flts.items()]
        ).count() >= 1

    def _value_processors(self, value, tbl_name, col, prcs, prc_type):
        col_type = type(self.tables[tbl_name].columns[col].type)
        prc_nms = prcs.get(col_type, {}).get(prc_type)
        if prc_nms:
            if type(prc_nms) is not list:
                raise DBException(f'processors "{prc_type}" for column "{col}" not list')
            for i, prc_nm in enumerate(prc_nms):
                prc_func = db_processors[prc_nm]
                active_logger.info(f'running processor "{prc_type}" #{i}, "{prc_nm}" on column "{col}"')
                value_out = prc_func(value)
                value = value_out
        return value

    def _process_columns(self, data, tbl_name, prcs, prc_type):
        self._validate_tbl(tbl_name)
        self._validate_cols(tbl_name, list(data.keys()))
        for col in data.keys():
            val_in = data[col]
            if val_in is None:
                active_logger.warning(f'table "{tbl_name}", col "{col}" value is None, skipping processing')
            else:
                val_out = self._value_processors(val_in, tbl_name, col, prcs, prc_type)
                data[col] = val_out

    def insert_row(self, tbl_name: str, data: Dict):
        active_logger.info(f'inserting row of information into table "{tbl_name}"')
        active_logger.info(f'keys passed are:\n'
                           f'{yaml.dump([str(k) for k in data.keys()])}')
        self._process_columns(data, tbl_name, self.col_prcs, 'process_in')
        row = self.Base.classes[tbl_name](**data)
        self.session.add(row)
        self.session.commit()

    def read_row(self, tbl_nm: str, pkey_flts: Dict) -> Dict:
        active_logger.info(f'reading row from table "{tbl_nm}" with filter "{pkey_flts}"')
        self._validate_tbl(tbl_nm)
        self._validate_pkeys(tbl_nm, pkey_flts)
        row = self.session.query(self.tables[tbl_nm]).filter(
            *[self.tables[tbl_nm].columns[k] == v for k, v in pkey_flts.items()]
        ).first()
        row_data = {str(k): v for k, v in dict(row).items()}  # convert sqlalchemy key objects to str for yaml
        self._process_columns(row_data, tbl_nm, self.col_prcs, 'process_out')
        return row_data


class DBCache(DBBase):

    # FILE_DICT = 'ROW_DICT_VALUES'

    def __init__(self, cache_root, cache_processors=None, **kwargs):
        super().__init__(**kwargs)
        self.cache_root = path.abspath(path.expandvars(cache_root))
        self.cache_prcs = cache_processors or dict()
        # self.dict_tbls = dict_tables or list()

    def cache_tbl(self, tbl_nm) -> str:
        return path.join(self.cache_root, tbl_nm)

    def cache_dir(self, tbl_nm: str, pkey_flts: Dict) -> str:
        return path.join(self.cache_tbl(tbl_nm), *pkey_flts.values())

    # def cache_dict_path(self, tbl_nm: str, pkey_flts: Dict) -> str:
    #     return path.join(self.cache_dir(tbl_nm, pkey_flts), self.FILE_DICT)

    def cache_col(self, tbl_nm: str, pkey_flts: Dict, col: str) -> str:
        return path.join(self.cache_dir(tbl_nm, pkey_flts), col)

    def clear_cache(self, tbl_nm: str, pkey_flts: Dict):
        active_logger.info(f'clearing cache from table "{tbl_nm}" with filters "{pkey_flts}"')
        p = self.cache_dir(tbl_nm, pkey_flts)
        if not path.exists(p):
            active_logger.info(f'path "{p}" does not exist, skipping')
        else:
            if not path.isdir(p):
                raise DBException(f'path "{p}" is not a directory')
            active_logger.info(f'removing cache dir: "{p}"')
            os.rmdir(p)

    def write_to_cache(self, tbl_nm: str, pkey_flts: Dict, data: Dict):
        self._validate_pkeys(tbl_nm, pkey_flts)
        self._validate_tbl(tbl_nm)
        d = self.cache_dir(tbl_nm, pkey_flts)
        active_logger.info(f'writing cache to path: "{d}"')
        if path.exists(d):
            active_logger.info('path already exists, exiting...')
            return
        os.makedirs(d, exist_ok=True)
        self._process_columns(data, tbl_nm, self.cache_prcs, 'process_out')
        for k in pkey_flts.keys():
            data.pop(k, None)
        # if tbl_nm in self.dict_tbls:
        #     p = self.cache_dict_path(tbl_nm, pkey_flts)
        #     active_logger.info(f'table "{tbl_nm}" specified to write as dict format, writing to "{p}"')
        #     with open(p, 'w') as f:
        #         f.write(yaml.dump(data))
        # else:
        for col in data.keys():
            if data[col] is None:
                active_logger.warning(f'column "{col}" value is none, skipping')
            else:
                p = self.cache_col(tbl_nm, pkey_flts, col)
                active_logger.info(f'writing column "{col}" to file: "{p}"')
                with open(p, 'w') as f:
                    f.write(data[col])

    def read_to_cache(self, tbl_nm: str, pkey_flts: Dict):
        active_logger.info(f'reading table "{tbl_nm}" row to cache with filters "{pkey_flts}"')
        data = self.read_row(tbl_nm, pkey_flts)
        self.write_to_cache(tbl_nm, pkey_flts, data)

    def insert_from_cache(self, tbl_nm, pkey_flts: Dict):
        active_logger.info(f'insert row to table "{tbl_nm}" from cache with filters "{pkey_flts}"')
        self._validate_pkeys(tbl_nm, pkey_flts)
        self._validate_tbl(tbl_nm)
        d = self.cache_dir(tbl_nm, pkey_flts)
        active_logger.info(f'getting files from cache directory: "{d}"')
        if not path.isdir(d):
            raise DBException(f'expected to be directory: "{d}"')
        data = pkey_flts.copy()
        # if tbl_nm in self.dict_tbls:
        #     p = self.cache_dict_path(tbl_nm, pkey_flts)
        #     active_logger.info(f'table "{tbl_nm}" specified to read as dict format, reading from "{p}"')
        #     with open(p, 'r') as f:
        #         fdata = yaml.load(f.read(), yaml.FullLoader)
        #         if type(fdata) is not dict:
        #             raise DBException(f'expected table "{tbl_nm}" data values read to be dict')
        #         data.update(fdata)
        # else:
        _, _, files = next(os.walk(d))
        self._validate_cols(tbl_nm, files)  # files should match column names
        for fnm in files:
            fp = self.cache_col(tbl_nm, pkey_flts, fnm)
            active_logger.info(f'reading column data from file: "{fp}"')
            with open(fp, 'r') as f:
                data[fnm] = f.read()
        self._process_columns(data, tbl_nm, self.cache_prcs, 'process_in')
        self.insert_row(tbl_nm, data)

    def _cache_pkeys(self, tbl_nm: str):
        """
        get list of primary key filters from nested dirs in cache
        """
        pkey_names = tuple(x.name for x in self.tables[tbl_nm].primary_key)
        def _get_pkeys(_dir: str, _base_pkey: Dict, _lvl) -> List:
            if not path.isdir(_dir):
                return []
            _, dirnames, _ = next(os.walk(_dir))
            return [_base_pkey | {pkey_names[_lvl]: d} for d in dirnames]

        lvl = 0
        flts = [{}]
        while lvl < len(pkey_names):
            flts_out = []
            for f in flts:
                d = self.cache_dir(tbl_nm, f)
                flts_out += _get_pkeys(d, f, lvl)
            flts = flts_out
            lvl += 1
        return flts

    def scan_cache(self, tbl_nm: str, post_insert: Optional[Callable[[str, Dict], None]] = None):
        tbl_root = self.cache_tbl(tbl_nm)
        active_logger.info(f'scanning for cached rows for table "{tbl_nm}" to insert in "{tbl_root}"')
        flts = self._cache_pkeys(tbl_nm)
        for pkey_filters in flts:
            if self.row_exist(tbl_nm, pkey_filters):
                active_logger.info(f'row "{pkey_filters}" already exists in database, skipping...')
            else:
                self.insert_from_cache(tbl_nm, pkey_filters)
                if post_insert is not None:
                    post_insert(tbl_nm, pkey_filters)

#
# DICT_TABLES = [
#     'marketmeta',
#     'strategymeta'
# ]

DB_PROCESSORS = {
    psqlbase.BYTEA: {
        'process_in': [
            'prc_compress'
        ],
        'process_out': [
            'prc_decompress',
        ]
    },
    psqljson.JSON: {
        'process_in': [
            'prc_json_encode',
        ],
        'process_out': [
            'prc_json_decode'
        ]
    }
}

CACHE_PROCESSORS = {
    psqlbase.BYTEA: {
        'process_in': [
            'prc_str_encode',
        ],
        'process_out': [
            'prc_str_decode'
        ]
    },
    psqlbase.TIMESTAMP: {
        'process_in': [
            'prc_dt_from_str',
        ],
        'process_out': [
            'prc_dt_to_str'
        ]
    },
    psqlbase.INTERVAL: {
        'process_in': [
            'prc_td_from_float',
        ],
        'process_out': [
            'prc_td_to_float'
        ]
    },
    psqljson.JSON: {
        'process_in': [
            'prc_json_decode',
        ],
        'process_out': [
            'prc_json_encode'
        ]
    }
}


class BettingDB(DBCache):
    """
    Betting database handler
    Manages session that connects to remote SQL ase for querying

    "Historic" markets to are files downloaded directly from betfair's historical data website
    "Recorded" markets are files from betfair markets recorded through a python script locally, which are recorded
    with the accompanying market catalogue file
    """
    def __init__(
            self,
            cache_root=r'%USERPROFILE%\Documents\_bf_cache',
            cache_processors=None,
            dict_tables=None,
            db_lang="postgresql",
            db_engine="psycopg2",
            db_user="better",
            db_host='imappalled.ddns.net',
            db_port=5432,
            db_name='betting',
            keyring_pwd_service="betdb_pwd",
            keyring_pwd_user='betting',
            col_processors=None,
    ):
        super().__init__(
            cache_root=cache_root,
            cache_processors=cache_processors or CACHE_PROCESSORS,
            # dict_tables=dict_tables or DICT_TABLES,
            db_lang=db_lang,
            db_engine=db_engine,
            db_user=db_user,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_pwd=keyring.get_password(keyring_pwd_service, keyring_pwd_user),
            col_processors=col_processors or DB_PROCESSORS
        )

    @staticmethod
    def get_meta(first_book: MarketBook, cat: MarketCatalogue = None) -> Dict:
        """
        Get metadata corresponding to the "Meta" table in the betting database for a given betfair Market

        Parameters
        ----------
        first_book : first MarketBook for betfair Market
        cat : if market is recorded and not historic, this needs to be passed to get
        venue and runner names

        Returns dict of metadata
        -------

        """
        mktdef: MarketDefinition = first_book.market_definition
        mktid = first_book.market_id
        init_time = first_book.publish_time
        pre_off = mktdef.market_time - init_time

        metadata = {
            'market_id': mktid,
            'sport_id': mktdef.event_type_id,
            'market_time': mktdef.market_time,
            'market_type': mktdef.market_type,
            'betting_type': mktdef.betting_type,
            'country_code': mktdef.country_code,
            'event_id': mktdef.event_id,
            'event_name': mktdef.event_name,  # historical
            'timezone': mktdef.timezone,
            'venue': mktdef.venue,
            'init_time': init_time,
            'pre_off': pre_off,
            'format': 'historic',
        }

        if cat is not None:
            metadata['event_name'] = cat.event.name
            metadata['venue'] = cat.event.venue
            metadata['format'] = 'recorded'

        return metadata

    @staticmethod
    def get_first_book(file_path: str) -> Optional[MarketBook]:
        """
        read the first line in a historical/streaming file and get the MarketBook parsed object, without reading or
        processing the rest of the file
        """
        with open(file_path) as f:
            l = f.readline()
        q = Queue()

        # stop it winging about stream latency by using infinity as max latency
        listener = StreamListener(q, max_latency=sys.float_info.max)
        listener.register_stream(0, 'marketSubscription')
        listener.on_data(l)
        return listener.output_queue.get()[0]

    def insert_market_meta(self, market_id: str):
        active_logger.info(f'creating metadata database entry for market "{market_id}"')
        pkey_flts = {'market_id': market_id}
        self.read_to_cache('marketstream', pkey_flts)
        stream_path = self.cache_col('marketstream', pkey_flts, 'stream_updates')
        bk = self.get_first_book(stream_path)
        cat = None
        cat_path = self.cache_col('marketstream', pkey_flts, 'catalogue')
        if path.exists(cat_path):
            if path.getsize(cat_path):
                with open(cat_path, 'r') as f:
                    cat_dict = json.loads(f.read())
                    try:
                        cat = MarketCatalogue(**cat_dict)
                    except TypeError as e:
                        raise DBException(f'failed to create market catalogue: {e}')
        if cat is None:
            names = {r.selection_id: r.name for r in bk.market_definition.runners}
        else:
            names = {r.selection_id: r.runner_name for r in cat.runners}
        for runner_id, name in names.items():
            active_logger.info(f'creating row for market "{market_id}", runner "{runner_id}", name "{name}"')
            self.insert_row('marketrunners', {
                'market_id': market_id,
                'runner_id': runner_id,
                'runner_name': name
            })
        meta_data = self.get_meta(bk, cat)
        self.insert_row('marketmeta', meta_data)

    def scan_mkt_cache(self):
        """
        scan marketstream cache files - insert into database if not exist and add corresponding marketmeta and runner rows
        """
        def mkt_post_insert(tbl_name, pkey_flts):
            if tbl_name != 'marketstream':
                raise DBException(f'expected "marketstream" table')
            self.insert_market_meta(pkey_flts['market_id'])
        self.scan_cache('marketstream', mkt_post_insert)

    def insert_strategy_runners(self, pkey_filters):
        p = self.cache_col('strategyupdates', pkey_filters, 'strategy_updates')
        if not path.isfile(p):
            raise DBException(f'expected strategy update file at "{p}"')
        df = TradeTracker.get_order_updates(p)
        active_logger.info(f'found {df.shape[0]} order updates in file "{p}"')
        if df.shape[0]:
            df = df[df['msg_type'] == MessageTypes.MSG_MARKET_CLOSE.name]
            df['profit'] = [TradeTracker.dict_order_profit(o) for o in df['order_info']]
            runner_profits = df.groupby(df['selection_id'])['profit'].sum().to_dict()
            for k, v in runner_profits.items():
                self.insert_row('strategyrunners', pkey_filters | {
                    'runner_id': k,
                    'profit': v
                })

    def scan_strat_cache(self):
        """
        scan strategy cache files - insert into database if not exist
        """
        def strat_post_insert(tbl_nm, pkey_flts):
            self.insert_strategy_runners(pkey_flts)

        self.scan_cache('strategymeta')
        self.scan_cache('strategyupdates', strat_post_insert)

    @property
    def market_meta_cols(self):
        return self.tables['marketmeta'].columns

    def market_update_paths(self, mkt_filters, limit=200):
        rows = self.session.query(
            self.tables['marketmeta'].columns['market_id']
        ).filter(*mkt_filters).limit(limit).all()
        update_paths = []
        for row in rows:
            mkt_flt = dict(row)
            self.read_to_cache('marketstream', mkt_flt)
            p = self.cache_col('marketstream', mkt_flt, 'stream_updates')
            if not path.isfile(p):
                raise DBException(f'expected file at stream update path: "{p}"')
            update_paths.append(p)
        return update_paths

    def runner_rows(self, market_id, strategy_id):
        """
        get filters rows of runners, joined with profit column from strategy
        """
        sr = self.tables['strategyrunners']
        cte_strat = self.session.query(
            sr.columns['runner_id'],
            sr.columns['profit'].label('runner_profit')
        ).filter(
            sr.columns['strategy_id'] == strategy_id,
            sr.columns['market_id'] == market_id
        ).cte()

        rn = self.tables['marketrunners']
        return self.session.query(
            rn,
            cte_strat.c['runner_profit'],
        ).join(
            cte_strat,
            rn.columns['runner_id'] == cte_strat.c['runner_id'],
            isouter=True,
        ).filter(
            rn.columns['market_id'] == market_id
        ).all()

    def _lost_ids(self, t1: Table, t2, id_col: str):
        """
        get a query for where table `t1` has rows that are not reflected in table `t2`, joined by a column with name
        specified by `id_col`. table `t2` can be a 1-to-1 mapping of rows from `t1` or 1 to many.

        E.g. if `t1` had an id column of 'sample_id_col' and some values [1,2,3], and `t2` had hundreds of rows but
        only with 'sample_id_col' equal to 1 or 2, then the function would return the 'sample_id_col' value of 3
        """
        cte = self.session.query(
            t2.columns[id_col]
        ).group_by(t2.columns[id_col]).cte()

        return self.session.query(
            t1.columns[id_col],
            cte.c[id_col]
        ).join(
            cte,
            t1.columns[id_col] == cte.c[id_col],
            isouter=True
        ).filter(cte.c[id_col] == None)

    def health_check(self):
        mkt_stm = self.tables['marketstream']
        mkt_met = self.tables['marketmeta']
        mkt_run = self.tables['marketrunners']

        # market stream/meta row counts
        n_mkt = self.session.query(mkt_stm).count()
        active_logger.info(f'{n_mkt} market stream rows')
        n_met = self.session.query(mkt_met).count()
        active_logger.info(f'{n_met} market meta rows')

        # market stream rows without corresponding market meta row
        q = self._lost_ids(mkt_stm, mkt_met, 'market_id')
        for row in q.all():
            active_logger.error(f'market "{row[0]}" does not have a meta row')

        # market runner meta row count
        nrun = self.session.query(mkt_run).count()
        active_logger.info(f'{nrun} market runner rows')

        # market stream rows without any corresponding runner rows
        q = self._lost_ids(mkt_stm, mkt_run, 'market_id')
        for row in q.all():
            active_logger.error(f'market "{row[0]}" does not have any runner rows')

        srt_met = self.tables['strategymeta']
        srt_run = self.tables['strategyrunners']
        srt_udt = self.tables['strategyupdates']

        # strategy meta & strategy market update row counts
        n_srtmet = self.session.query(srt_met).count()
        active_logger.info(f'{n_srtmet} strategy meta rows found')
        n_srtudt = self.session.query(srt_udt).count()
        active_logger.info(f'{n_srtudt} strategy market update rows found')

        # strategy meta rows without any strategy update rows
        q = self._lost_ids(srt_met, srt_udt, 'strategy_id')
        for row in q.all():
            active_logger.error(f'strategy "{row[0]}" does not have any market updates')

        # strategy runner row count
        n_srtrun = self.session.query(srt_run).count()
        active_logger.info(f'{n_srtrun} strategy runner rows found')

        # strategy meta rows without any strategy runner rows
        q = self._lost_ids(srt_met, srt_run, 'strategy_id')
        for row in q.all():
            active_logger.error(f'strategy "{row[0]}" does not have any runner rows')

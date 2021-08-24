from __future__ import annotations

import shutil
from betfairlightweight.resources.streamingresources import MarketDefinition
from betfairlightweight.resources.bettingresources import MarketCatalogue, MarketBook
from betfairlightweight.streaming.listener import StreamListener
import sqlalchemy
from sqlalchemy.sql.selectable import CTE
from sqlalchemy import create_engine, func, DECIMAL
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Table
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.dialects.postgresql import base as psqlbase
from sqlalchemy.dialects.postgresql import json as psqljson
from sqlalchemy.sql.functions import sum as sql_sum
from sqlalchemy_filters.filters import Operator as SqlOperator
from sqlalchemy.orm.query import Query
from queue import Queue
import logging
from typing import Optional, Dict, List, Callable, Any, Tuple
import keyring
from os import path
import os
from datetime import datetime, timedelta
import zlib
import yaml
import json
import sys
import dateparser

from myutils import mydict, registrar
from ..exceptions import DBException
from .dbfilter import DBFilterHandler

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

db_processors = registrar.Registrar()


@db_processors.register_element
def prc_str_to_dt(data):
    return dateparser.parse(data, settings={'DATE_ORDER': 'DMY'})  # use UK day-month-year instead of US month-day-year


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

    def apply_basic_filters(self, tbl_nm: str, pkey_flts: Dict) -> Query:
        return self.session.query(self.tables[tbl_nm]).filter(
            *[self.tables[tbl_nm].columns[k] == v for k, v in pkey_flts.items()]
        )

    def row_exist(self, tbl_nm: str, pkey_flts: Dict) -> bool:
        """
        Determine if row(s) exist in database for a given table
        """
        return self.apply_basic_filters(tbl_nm, pkey_flts).count() >= 1

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

    def read_rows(self, tbl_nm: str, pkey_flts: Dict) -> List[Dict]:
        active_logger.info(f'reading rows from table "{tbl_nm}" with filter "{pkey_flts}"')
        self._validate_tbl(tbl_nm)
        self._validate_pkeys(tbl_nm, pkey_flts)
        if not self.row_exist(tbl_nm, pkey_flts):
            raise DBException(f'row in table "{tbl_nm}" with filters "{pkey_flts}" does not exist')

        sql_rows = self.apply_basic_filters(tbl_nm, pkey_flts).all()
        rows = []
        for row in sql_rows:
            row_dict = {
                str(k): v
                for k, v in dict(row).items()
            }  # convert sqlalchemy key objects to str for yaml
            self._process_columns(row_dict, tbl_nm, self.col_prcs, 'process_out')
            rows.append(row_dict)
        return rows

    def read_row(self, tbl_nm: str, pkey_flts: Dict) -> Dict:
        rows = self.read_rows(tbl_nm, pkey_flts)
        if len(rows) != 1:
            raise DBException(f'expected 1 row from table "{tbl_nm}" with filters "{pkey_flts}", got {len(rows)}')
        return rows[0]

    def delete_rows(self, tbl_nm: str, pkey_flts: Dict) -> int:
        active_logger.info(f'deleting rows from table "{tbl_nm}" with filters: "{pkey_flts}"')
        q = self.apply_basic_filters(tbl_nm, pkey_flts)
        ret = q.delete(synchronize_session='fetch')
        self.session.commit()
        return ret

    def order_query(self, query: Query, cols, order_col: str, order_asc: bool):
        """apply ordering based on column of cte"""
        if order_col not in cols:
            raise DBException(f'cannot order by column "{order_col}", does not exist in CTE')
        order_func = sqlalchemy.asc if order_asc else sqlalchemy.desc
        return query.order_by(order_func(cols[order_col]))


class DBCache(DBBase):

    def __init__(self, cache_root, cache_processors=None, **kwargs):
        super().__init__(**kwargs)
        self.cache_root = path.abspath(path.expandvars(cache_root))
        if not path.isdir(self.cache_root):
            active_logger.info(f'creating cache root directory at: "{self.cache_root}"')
            os.makedirs(self.cache_root)
        else:
            active_logger.info(f'existing cache root directory found at: "{self.cache_root}"')
        self.cache_prcs = cache_processors or dict()

    def cache_tbl(self, tbl_nm) -> str:
        return path.join(self.cache_root, tbl_nm)

    def cache_dir(self, tbl_nm: str, pkey_flts: Dict) -> str:
        return path.join(self.cache_tbl(tbl_nm), *pkey_flts.values())

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

    def scan_cache(self, tbl_nm: str, post_insert: Optional[Callable[[str, Dict], None]] = None) -> List[Dict]:
        tbl_root = self.cache_tbl(tbl_nm)
        active_logger.info(f'scanning for cached rows for table "{tbl_nm}" to insert in "{tbl_root}"')
        flts = self._cache_pkeys(tbl_nm)
        added_pkeys = []
        for pkey_filters in flts:
            if self.row_exist(tbl_nm, pkey_filters):
                active_logger.info(f'row "{pkey_filters}" already exists in database, skipping...')
            else:
                self.insert_from_cache(tbl_nm, pkey_filters)
                added_pkeys.append(pkey_filters)
                if post_insert is not None:
                    post_insert(tbl_nm, pkey_filters)
        return added_pkeys

    def wipe_cache(self) -> Tuple[int, int]:
        active_logger.info(f'clearing cache root at "{self.cache_root}"')
        _, dirnames, filenames = next(os.walk(self.cache_root))
        for fnm in filenames:
            p = path.join(self.cache_root, fnm)
            os.remove(p)
        for dnm in dirnames:
            p = path.join(self.cache_root, dnm)
            shutil.rmtree(p)
        return len(filenames), len(dirnames)


DB_PROCESSORS = {
    psqlbase.BYTEA: {
        'process_in': [
            'prc_compress'
        ],
        'process_out': [
            'prc_decompress',
        ]
    },
    # sqlalchemy automatically converts JSON to/from dictionary objects

    # psqljson.JSON: {
    #     'process_in': [
    #         'prc_json_encode',
    #     ],
    #     'process_out': [
    #         'prc_json_decode'
    #     ]
    # }
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

FILTER_SPEC_PROCESSORS = {
    psqlbase.TIMESTAMP: {
        'processors': [
            'prc_str_to_dt'
        ]
    }
}

MARKET_FILTER_SPEC = {
    'value': {
        'type': object,
    },
    'field': {
        'type': str,
    },
    'op': {
        'type': str,
    }
}


def apply_filter_spec(tbl: Table, q: Query, filters_spec: List[Dict]) -> Query:
    """sqlalchemy_filters `apply_filters` function doesn't work with Sqlalchemy V1.14 so i've bodged it myself until
    they sort it out"""
    conditions = [
        SqlOperator.OPERATORS[f['op']](tbl.columns[f['field']], f['value'])
        for f in filters_spec
    ]
    return q.filter(*conditions)


class BettingDB:
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
        self._dbc = DBCache(
            cache_root=cache_root,
            cache_processors=cache_processors or CACHE_PROCESSORS,
            db_lang=db_lang,
            db_engine=db_engine,
            db_user=db_user,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_pwd=keyring.get_password(keyring_pwd_service, keyring_pwd_user),
            col_processors=col_processors or DB_PROCESSORS
        )

    def close(self):
        self._dbc.session.close()

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
        self._dbc.read_to_cache('marketstream', pkey_flts)
        stream_path = self._dbc.cache_col('marketstream', pkey_flts, 'stream_updates')
        bk = self.get_first_book(stream_path)
        cat = None
        cat_path = self._dbc.cache_col('marketstream', pkey_flts, 'catalogue')
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
            self._dbc.insert_row('marketrunners', {
                'market_id': market_id,
                'runner_id': runner_id,
                'runner_name': name
            })
        meta_data = self.get_meta(bk, cat)
        self._dbc.insert_row('marketmeta', meta_data)

    def insert_strategy_runners(self, pkey_filters, profit_func: Callable[[str], Dict]):
        p = self._dbc.cache_col('strategyupdates', pkey_filters, 'strategy_updates')
        if not path.isfile(p):
            raise DBException(f'expected strategy update file at "{p}"')
        runner_profits = profit_func(p)
        for k, v in runner_profits.items():
            self._dbc.insert_row('strategyrunners', pkey_filters | {
                'runner_id': k,
                'profit': v
            })

    def wipe_cache(self) -> Tuple[int, int]:
        return self._dbc.wipe_cache()

    def scan_mkt_cache(self) -> List[Dict]:
        """
        scan marketstream cache files - insert into database if not exist and add corresponding marketmeta and runner rows
        """
        def mkt_post_insert(tbl_name, pkey_flts):
            if tbl_name != 'marketstream':
                raise DBException(f'expected "marketstream" table')
            self.insert_market_meta(pkey_flts['market_id'])
        return self._dbc.scan_cache('marketstream', mkt_post_insert)

    def scan_strat_cache(self, profit_func: Callable[[str], Dict]) -> List[Dict]:
        """
        scan strategy cache files - insert into database if not exist
        """
        def strat_post_insert(tbl_nm, pkey_flts):
            self.insert_strategy_runners(pkey_flts, profit_func)

        added_keys = self._dbc.scan_cache('strategymeta')
        self._dbc.scan_cache('strategyupdates', strat_post_insert)
        return added_keys

    def write_strat_info(self, strategy_id, type: str, name: str, exec_time: datetime, info: dict):
        data = {
            'type': type,
            'name': name,
            'exec_time': exec_time,
            'info': info
        }
        self._dbc.write_to_cache(
            tbl_nm='strategymeta',
            pkey_flts={
                'strategy_id': str(strategy_id)
            },
            data=data
        )

    def path_mkt_usr_updates(self, market_id) -> str:
        return self._dbc.cache_col(
            tbl_nm='marketstream',
            pkey_flts={
                'market_id': market_id
            },
            col='user_data'
        )

    def path_mkt_cat(self, market_id) -> str:
        return self._dbc.cache_col(
            tbl_nm='marketstream',
            pkey_flts={
                'market_id': market_id
            },
            col='catalogue',
        )

    def path_mkt_updates(self, market_id) -> str:
        return self._dbc.cache_col(
            tbl_nm='marketstream',
            pkey_flts={
                'market_id': market_id
            },
            col='stream_updates',
        )

    def path_strat_features(self, market_id, strategy_id) -> str:
        return self._dbc.cache_col(
            tbl_nm='strategyupdates',
            pkey_flts={
                'strategy_id': str(strategy_id),
                'market_id': market_id,
            },
            col='strategy_features'
        )

    def path_strat_updates(self, market_id, strategy_id) -> str:
        return self._dbc.cache_col(
            tbl_nm='strategyupdates',
            pkey_flts={
                'strategy_id': str(strategy_id),
                'market_id': market_id
            },
            col='strategy_updates'
        )

    def paths_market_updates(self, filter_spec: List[Dict], limit=200):
        for flt in filter_spec:
            mydict.validate_config(flt, MARKET_FILTER_SPEC)
            flt['value'] = self._dbc._value_processors(
                value=flt['value'],
                tbl_name='marketmeta',
                col=flt['field'],
                prcs=FILTER_SPEC_PROCESSORS,
                prc_type='processors'
            )
        tbl = self._dbc.tables['marketmeta']
        q = self._dbc.session.query(tbl)
        q_flt = apply_filter_spec(tbl, q, filter_spec)
        rows = q_flt.limit(limit).all()
        update_paths = []
        for row in rows:
            mkt_flt = {'market_id': row.market_id}
            self._dbc.read_to_cache('marketstream', mkt_flt)
            p = self._dbc.cache_col('marketstream', mkt_flt, 'stream_updates')
            if not path.isfile(p):
                raise DBException(f'expected file at stream update path: "{p}"')
            update_paths.append(p)
        return update_paths

    def rows_runners(self, market_id, strategy_id) -> List[Dict]:
        """
        get filters rows of runners, joined with profit column from strategy
        """
        sr = self._dbc.tables['strategyrunners']
        cte_strat = self._dbc.session.query(
            sr.columns['runner_id'],
            sr.columns['profit'].label('runner_profit')
        ).filter(
            sr.columns['strategy_id'] == strategy_id,
            sr.columns['market_id'] == market_id
        ).cte()

        rn = self._dbc.tables['marketrunners']
        rows = self._dbc.session.query(
            rn,
            cte_strat.c['runner_profit'],
        ).join(
            cte_strat,
            rn.columns['runner_id'] == cte_strat.c['runner_id'],
            isouter=True,
        ).filter(
            rn.columns['market_id'] == market_id
        ).all()
        return [dict(row) for row in rows]

    def rows_market(self, cte, col_names, max_rows, order_col=None, order_asc=False) -> List[Dict]:
        cols = [cte.c[nm] for nm in col_names]
        q = self._dbc.session.query(*cols)
        if order_col is not None:
            q = self._dbc.order_query(q, cte.c, order_col, order_asc)
        rows = q.limit(max_rows).all()
        return [dict(row) for row in rows]

    # TODO - implement in UI
    def rows_strategy(self, max_rows) -> List[Dict]:
        shn = self._dbc.session
        sm = self._dbc.tables['strategymeta']
        sr = self._dbc.tables['strategyrunners']
        p_cte = shn.query(
            sr.columns['strategy_id'],
            func.sum(sr.columns['profit']).label('total_profit')
        ).group_by(sr.columns['strategy_id']).cte()
        shn.query(
            sm,
            p_cte.c['total_profit']
        ).join(p_cte, sm.columns['strategy_id'] == p_cte.c['strategy_id'])
        m_cte = shn.query(sr.c['strategy_id'], sr.c['market_id']).distinct().cte()
        m_cte = shn.query(
            m_cte.c['strategy_id'],
            func.count(m_cte.c['market_id']).label('n_markets')
        ).group_by(m_cte.c['strategy_id']).cte()
        q = shn.query(sm, p_cte.c['total_profit'], m_cte.c['n_markets']).join(
            p_cte, sm.c['strategy_id'] == p_cte.c['strategy_id'], isouter=True
        ).join(
            m_cte, sm.c['strategy_id'] == m_cte.c['strategy_id'], isouter=True
        )
        return [dict(row) for row in q.limit(max_rows).all()]

    def filters_labels(self, filters: DBFilterHandler, cte) -> List[List[Dict[str, Any]]]:
        return filters.filters_labels(self._dbc.session, self._dbc.tables, cte)

    def cte_count(self, cte: CTE) -> int:
        return self._dbc.session.query(cte).count()

    def strategy_count(self) -> int:
        return self._dbc.session.query(self._dbc.tables['strategymeta']).count()

    def strategy_delete(self, strategy_id) -> Tuple[int, int ,int]:
        strategy_id = str(strategy_id)
        active_logger.info(f'attempting to delete strategy: "{strategy_id}"')
        pkey_flt = {'strategy_id': strategy_id}
        if not self._dbc.row_exist('strategymeta', pkey_flt):
            raise DBException(f'strategy does not exist, using filters: "{pkey_flt}"')
        if not strategy_id:
            raise DBException(f'trying to delete strategy where ID passed is blank!')
        rows = self._dbc.read_rows('strategymeta', pkey_flt)
        if len(rows) != 1:
            raise DBException(f'expected 1 strategy meta row with filter: "{pkey_flt}"')
        n_runners = self._dbc.delete_rows('strategyrunners', pkey_flt)
        active_logger.info(f'deleted {n_runners} rows from "strategyrunners" table')
        n_mkts = self._dbc.delete_rows('strategyupdates', pkey_flt)
        active_logger.info(f'deleted {n_mkts} rows from "strategyupdates" table')
        n_meta = self._dbc.delete_rows('strategymeta', pkey_flt)
        active_logger.info(f'deleted {n_meta} rows from "strategymeta" table')
        return n_meta, n_mkts, n_runners

    def filters_strat_cte(self, strat_filters: DBFilterHandler) -> CTE:
        """
        get filtered database strategy common table expression (CTE)
        """
        strat_meta = self._dbc.tables['strategymeta']
        q = self._dbc.session.query(strat_meta).filter(
            *strat_filters.filters_conditions(strat_meta)
        )
        return q.cte()

    def filters_mkt_cte(self, strategy_id, mkt_filters: DBFilterHandler) -> CTE:
        meta = self._dbc.tables['marketmeta']
        sr = self._dbc.tables['strategyrunners']

        if strategy_id:
            strat_cte = self._dbc.session.query(
                sr.columns['market_id'],
                sql_sum(sr.columns['profit']).label('market_profit')
            ).filter(
                sr.columns['strategy_id'] == strategy_id
            ).group_by(
                sr.columns['market_id']
            ).cte()

            q = self._dbc.session.query(
                meta,
                strat_cte.c['market_profit']
            ).join(
                strat_cte,
                meta.columns['market_id'] == strat_cte.c['market_id']
            )
        else:
            q = self._dbc.session.query(
                meta,
                sqlalchemy.null().label('market_profit')
            )

        q = q.filter(*mkt_filters.filters_conditions(meta))
        return q.cte()

    def cache_strat_updates(self, strategy_id, market_id):
        pkey_flts = {
            'strategy_id': str(strategy_id),
            'market_id': market_id
        }
        self._dbc.read_to_cache('strategyupdates', pkey_flts)

    def cache_strat_meta(self, strategy_id):
        pkey_flt = {'strategy_id': strategy_id}
        self._dbc.read_to_cache('strategymeta', pkey_flt)

    def cache_mkt_stream(self, market_id):
        pkey_flt = {'market_id': market_id}
        self._dbc.read_to_cache('marketstream', pkey_flt)

    def read_mkt_meta(self, market_id) -> Dict:
        pkey_flt = {'market_id': market_id}
        return self._dbc.read_row('marketmeta', pkey_flt)

    def _lost_ids(self, t1: Table, t2, id_col: str):
        """
        get a query for where table `t1` has rows that are not reflected in table `t2`, joined by a column with name
        specified by `id_col`. table `t2` can be a 1-to-1 mapping of rows from `t1` or 1 to many.

        E.g. if `t1` had an id column of 'sample_id_col' and some values [1,2,3], and `t2` had hundreds of rows but
        only with 'sample_id_col' equal to 1 or 2, then the function would return the 'sample_id_col' value of 3
        """
        cte = self._dbc.session.query(
            t2.columns[id_col]
        ).group_by(t2.columns[id_col]).cte()

        return self._dbc.session.query(
            t1.columns[id_col],
            cte.c[id_col]
        ).join(
            cte,
            t1.columns[id_col] == cte.c[id_col],
            isouter=True
        ).filter(cte.c[id_col] == None)

    def health_check(self):
        mkt_stm = self._dbc.tables['marketstream']
        mkt_met = self._dbc.tables['marketmeta']
        mkt_run = self._dbc.tables['marketrunners']

        # market stream/meta row counts
        n_mkt = self._dbc.session.query(mkt_stm).count()
        active_logger.info(f'{n_mkt} market stream rows')
        n_met = self._dbc.session.query(mkt_met).count()
        active_logger.info(f'{n_met} market meta rows')

        # market stream rows without corresponding market meta row
        q = self._lost_ids(mkt_stm, mkt_met, 'market_id')
        for row in q.all():
            active_logger.error(f'market "{row[0]}" does not have a meta row')

        # market runner meta row count
        nrun = self._dbc.session.query(mkt_run).count()
        active_logger.info(f'{nrun} market runner rows')

        # market stream rows without any corresponding runner rows
        q = self._lost_ids(mkt_stm, mkt_run, 'market_id')
        for row in q.all():
            active_logger.error(f'market "{row[0]}" does not have any runner rows')

        srt_met = self._dbc.tables['strategymeta']
        srt_run = self._dbc.tables['strategyrunners']
        srt_udt = self._dbc.tables['strategyupdates']

        # strategy meta & strategy market update row counts
        n_srtmet = self._dbc.session.query(srt_met).count()
        active_logger.info(f'{n_srtmet} strategy meta rows found')
        n_srtudt = self._dbc.session.query(srt_udt).count()
        active_logger.info(f'{n_srtudt} strategy market update rows found')

        # strategy meta rows without any strategy update rows
        q = self._lost_ids(srt_met, srt_udt, 'strategy_id')
        for row in q.all():
            active_logger.error(f'strategy "{row[0]}" does not have any market updates')

        # strategy runner row count
        n_srtrun = self._dbc.session.query(srt_run).count()
        active_logger.info(f'{n_srtrun} strategy runner rows found')

        # strategy meta rows without any strategy runner rows
        q = self._lost_ids(srt_met, srt_run, 'strategy_id')
        for row in q.all():
            active_logger.error(f'strategy "{row[0]}" does not have any runner rows')

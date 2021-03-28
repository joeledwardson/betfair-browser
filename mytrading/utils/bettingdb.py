from mytrading.utils.storage import get_historical, get_first_book, get_hist_cat
from mytrading.utils.storage import RE_MARKET_ID, EXT_CATALOGUE, EXT_RECORDED
from betfairlightweight.resources.streamingresources import MarketDefinition
from betfairlightweight.resources.bettingresources import MarketCatalogue, MarketBook
import logging
from typing import Optional, Dict
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import select, distinct
from sqlalchemy.sql.schema import Table
from sqlalchemy.ext.automap import automap_base
import keyring
import zlib
from os import walk, path
import re
from datetime import datetime


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class BettingDB:
    """
    Vetting database handler
    Manages session that connects to remote SQL database for querying

    "Historic" markets to are files downlaoded directly from betfair's historical data website
    "Recorded" markets are files from betfair markets recorded through a python script locally, which are recorded
    with the accompanying market catalogue file
    """
    def __init__(
            self,
            db_lang="postgresql",
            db_engine="psycopg2",
            db_user="better",
            db_host='imappalled.ddns.net',
            db_port=5432,
            db_name='betting',
            keyring_pwd_service="betdb_pwd",
            keyring_pwd_user='betting'):

        engine_str = f'+{db_engine}' if db_engine else ''

        self.Base = automap_base()

        self.engine = create_engine(
            f'{db_lang}{engine_str}://{db_user}'
            f':{keyring.get_password(keyring_pwd_service, keyring_pwd_user)}'
            f'@{db_host}:{db_port}/{db_name}'
        )

        self.Base.prepare(self.engine, reflect=True)
        self.session = Session(self.engine)

        self.tables: Dict[str, Table] = self.Base.metadata.tables


    def get_country_codes(self) -> Dict:
        """
        get dictionary of {country code: name}
        """
        t = self.Base.metadata.tables['countrycodes']
        self.session.query(t['alpha_2_code'])

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
            'betfair_id': mktid,
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
            'runner_names': {r.selection_id: r.name for r in mktdef.runners} # historical
        }

        if cat is not None:
            metadata['event_name'] = cat.event.name
            metadata['venue'] = cat.event.venue
            metadata['runner_names'] = {
                r.selection_id: r.runner_name
                for r in cat.runners
            }

        return metadata

    def id_exist(self, betfair_id, table_class) -> bool:
        """
        Determine if row(s) exist in database for a given table and betfair ID
        """
        return bool(self.session.query(table_class).filter_by(betfair_id=betfair_id).count())

    def insert_market(self, data, meta: Dict, catalogue: Optional[MarketCatalogue]=None) -> bool:
        """
        Insert row(s) into database table(s) for Meta and streaming info given streaming data and market metadata
        Return True on success
        """
        betfair_id = meta['betfair_id']
        if self.id_exist(betfair_id, self.Meta) or self.id_exist(betfair_id, self.Stream):
            active_logger.warning(f'betfair id {betfair_id} already exist in meta or stream')
            return False

        compressed = zlib.compress(data.encode())
        stream_row = self.Stream(
            betfair_id=betfair_id,
            format='historic' if catalogue else 'recorded',
            data=compressed,
            catalogue=catalogue.json() if catalogue else None,
        )

        meta_row = self.Meta(**meta)

        try:
            self.session.add(stream_row)
            self.session.add(meta_row)
            self.session.commit()
            active_logger.info(f'Put "{betfair_id}" to database')
            return True
        except Exception as e:
            active_logger.warning(f'Exception putting "{betfair_id}" to DB: {e}')
            return False


def market_to_db(db: BettingDB, stream_path: str, cat_path: str = None) -> bool:
    """
    Insert row(s) into database table(s) for Meta and streaming info for a given historic/streaming file and its
    corresponding catalogue (only needed if type is recorded, not historic)

    Parameters
    ----------
    stream_path : path to historic/recorded file
    cat_path : (optional) path to catalogue

    Returns True on success
    -------

    """
    with open(stream_path) as f:
        data = f.read()

    cat = None
    if cat_path:
        cat = get_hist_cat(cat_path)
        if cat is None:
            return False

    bk = get_first_book(stream_path)
    if bk is None:
        return False

    meta = db.get_meta(bk, cat)
    return db.insert_market(data, meta, cat)


def dir_to_db(db: BettingDB, dirpath: str) -> None:
    """
    Process a directory recursively, attempting to find historic market file(s) and recorded/catalogue market file
    pair(s) and add them to the betting database

    Parameters
    ----------
    dirpath : directory to search
    -------

    """

    for dirpath, dirnames, filenames in walk(dirpath):
        for filename in filenames:

            filepath = path.join(dirpath, filename)
            file, ext = path.splitext(filepath)

            if re.match(RE_MARKET_ID, filename):
                market_to_db(db, filepath)
            elif ext == EXT_RECORDED:
                cat_path = file + EXT_CATALOGUE
                if path.exists(cat_path):
                    market_to_db(db, filepath, cat_path)
                else:
                    active_logger.warning(f'"{filepath}" <- recorded file\n'
                                          f'"{cat_path}" <- catalogue file not found')


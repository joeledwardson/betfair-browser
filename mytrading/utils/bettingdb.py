
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

    def id_exist(self, market_id, table_class) -> bool:
        """
        Determine if row(s) exist in database for a given table and betfair ID
        """
        return bool(self.session.query(table_class).filter_by(market_id=market_id).count())

    def insert_market(self, data, meta: Dict, names: Dict, catalogue: Optional[MarketCatalogue]=None) -> bool:
        """
        Insert row(s) into database table(s) for Meta and streaming info given streaming data and market metadata
        Return True on success
        """
        tbl_meta = self.tables['marketmeta']
        tbl_stream = self.tables['marketstream']
        tbl_runners = self.tables['runners']
        cls_meta = self.Base.classes['marketmeta']
        cls_stream = self.Base.classes['marketstream']
        cls_runner = self.Base.classes['runners']
        new_rows = []

        market_id = meta['market_id']
        if self.id_exist(market_id, tbl_meta) or self.id_exist(market_id, tbl_stream) or \
                self.id_exist(market_id, tbl_runners):
            active_logger.warning(f'betfair id {market_id} already exist in meta/stream/runners')
            return False

        compressed = zlib.compress(data.encode())
        stream_row = cls_stream(
            market_id=market_id,
            data=compressed,
            catalogue=catalogue.json() if catalogue else None,
        )
        new_rows.append(stream_row)

        meta_row = cls_meta(**meta)
        new_rows.append(meta_row)

        for _id, name in names.items():
            runner_row = cls_runner(market_id=market_id, runner_id=_id, runner_name=name)
            new_rows.append(runner_row)

        try:
            for row in new_rows:
                self.session.add(row)
            self.session.commit()
            active_logger.info(f'Put "{market_id}" to database')
            return True
        except Exception as e:
            active_logger.warning(f'Exception putting "{market_id}" to DB: {e}')
            return False

import betfairlightweight
from betfairlightweight.filters import market_filter
from betfairlightweight.resources import MarketCatalogue
from betfairlightweight import APIClient
import logging
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd
import os
import keyring
from os import path
import shutil
import re
from queue import Queue
import sys

from myutils.mygeneric import dgetattr
from ..process import bf_dt
from .bettingdb import BettingDB

RE_EVENT = r'^\d{8}$'
RE_MARKET_ID = r'^\d\.\d{9}$'
EXT_CATALOGUE = '.bfcatalogue'
EXT_RECORDED = '.bfrecorded'

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class APIHandler:
    MAX_CATALOGUES = 100
    DEF_CAT_ATTRS = {
        'market ID': 'market_id',
        'market name': 'market_name',
        'event type ID': 'event_type.id',
        'event type name': 'event_type.name',
        'event ID': 'event.id',
        'event country': 'event.country_code',
        'event name': 'event.name',
        'start time': 'market_start_time',
    }

    def __init__(self):
        """initialise from locally stored betfair certification, username and password"""
        self._certs_path = os.environ['USERPROFILE'] + r'\OneDrive\Betfair\bf certs'
        self._my_username = keyring.get_password('bf_username', 'joel')
        self._my_password = keyring.get_password('bf_password', 'joel')
        self._my_app_key = keyring.get_password('bf_app_key', 'joel')
        self._api_client = APIClient(
            username=self._my_username,
            password=self._my_password,
            app_key=self._my_app_key,
            certs=self._certs_path
        )

    @property
    def API_client(self):
        """Get Betfair API client with credentials"""
        return self._api_client

    def list_market_catalogues(
        self,
        event_type_ids: Optional[List[str]] = None,
        market_type_codes: Optional[List[str]] = None,
        market_betting_types: Optional[List[str]] = None,
        market_limit: int = 0,
        market_countries: Optional[List[str]] = None,
        from_datetime: Optional[datetime] = None,
        to_datetime: Optional[datetime] = None,
        sort='FIRST_TO_START',
    ) -> List[MarketCatalogue]:
        """list market catalogues"""

        # get all info from market catalogues (except competitions)
        market_projection = ['EVENT',
                             'EVENT_TYPE',
                             'MARKET_START_TIME',
                             'MARKET_DESCRIPTION',
                             'RUNNER_DESCRIPTION']

        race_filter = market_filter(
            event_type_ids=event_type_ids,
            market_type_codes=market_type_codes,
            market_betting_types=market_betting_types,
            market_countries=market_countries,
            market_start_time={
                'from': bf_dt(from_datetime) if from_datetime else None,
                'to': bf_dt(to_datetime) if to_datetime else None,
            }
        )

        # get market catalogues
        return self._api_client.betting.list_market_catalogue(
            filter=race_filter,
            market_projection=market_projection,
            max_results=market_limit or self.MAX_CATALOGUES,
            sort=sort
        )

    @classmethod
    def bf_catalogues_to_df(
            cls,
            market_catalogues: List[MarketCatalogue],
            attrs: Optional[Dict] = None
    ) -> pd.DataFrame:
        """convert list of market catalogues to dataframe, columns specified by `attrs` dict of (col => catalogue
        attribute)"""
        if attrs is None:
            attrs = cls.DEF_CAT_ATTRS
        data = [{
            k: dgetattr(cat, v)
            for k, v in attrs.items()
        } for cat in market_catalogues]
        return pd.DataFrame(data)

    def get_historical(self, stream_path: str) -> Queue:
        """Get Queue object from historical Betfair data file"""
        output_queue = Queue()
        # stop it winging about stream latency by using infinity as max latency
        listener = betfairlightweight.StreamListener(
            output_queue=output_queue,
            max_latency=sys.float_info.max
        )
        stream = self._api_client.streaming.create_historical_stream(
            file_path=stream_path,
            listener=listener
        )
        stream.start()
        return output_queue


def migrate_mkt_cache(db: BettingDB, market_id: str, stream_path: str, cat_path: str = None):
    """
    migrate a market stream (and optionally catalogue) file(s) to database cache location
    this is a utility tool for migrating from the old style of file storage with hierarchical file structuring according
    to Betfair historical with (year => month => day => event) ...etc and .RECORDED filetyes
    """
    d = db.cache_dir('marketstream', {'market_id': market_id})
    os.makedirs(d, exist_ok=True)
    stream_dest = path.join(d, 'stream_updates')
    shutil.copy(stream_path, stream_dest)
    active_logger.info(f'migrating stream from "{stream_path}" to cache "{stream_dest}')
    if cat_path is not None:
        cat_dest = path.join(d, 'catalogue')
        active_logger.info(f'migrating catalogue from "{cat_path}" to cache "{cat_dest}"')
        shutil.copy(cat_path, cat_dest)


def migrate_dir_cache(db: BettingDB, mkts_dir: str) -> None:
    """
    Process a directory recursively, attempting to find historic market file(s) and recorded/catalogue market file
    pair(s) and add them to the betting database
    """
    for d, d_names, f_names in os.walk(mkts_dir):
        for f_name in f_names:
            f_path = path.join(d, f_name)
            f_root, ext = path.splitext(f_path)
            if re.match(RE_MARKET_ID, f_name):
                active_logger.info(f'processing file "{f_path}"')
                migrate_mkt_cache(db, f_name, f_name)  # for historical file name is market ID
            elif ext == EXT_RECORDED:
                cat_path = f_root + EXT_CATALOGUE
                active_logger.info(f'processing file "{f_path}"')
                if path.exists(cat_path):
                    migrate_mkt_cache(db, f_root, f_path, cat_path)  # for recorded, market ID is file root
                else:
                    active_logger.warning(f'"{f_path}" <- recorded file\n'
                                          f'"{cat_path}" <- catalogue file not found')
                    continue





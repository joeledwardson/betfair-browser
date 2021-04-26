import logging
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd
from betfairlightweight import APIClient
import os
import keyring
from betfairlightweight.filters import market_filter
from betfairlightweight.resources import MarketCatalogue

from ..process import bf_dt
from myutils.generic import dgetattr


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class BFSecurity:
    # locally stored betfair certification, username and password
    def __init__(self):
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


class BfUtils:
    MAX_CATALOGUES = 1000
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

    @classmethod
    def list_market_catalogues(
        cls,
        trading: APIClient,
        event_type_id: str,
        market_type_code: str,
        market_betting_type: str,
        market_limit: int,
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
            event_type_ids=[event_type_id],
            market_type_codes=[market_type_code],
            market_betting_types=[market_betting_type],
            market_countries=market_countries,
            market_start_time={
                'from': bf_dt(from_datetime) if from_datetime else None,
                'to': bf_dt(to_datetime) if to_datetime else None,
            }
        )

        # get market catalogues
        return trading.betting.list_market_catalogue(
            filter=race_filter,
            market_projection=market_projection,
            max_results=market_limit or cls.MAX_CATALOGUES,
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


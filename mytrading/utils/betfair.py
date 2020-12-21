from betfairlightweight import APIClient
from datetime import datetime
from typing import List, Optional, Dict
from betfairlightweight.resources.bettingresources import MarketCatalogue
from betfairlightweight.filters import market_filter
from mytrading.process.times import bf_dt
import pandas as pd
from myutils.generic import dgetattr


def bf_list_market_catalogue(
    trading: APIClient,
    event_type_id: str,
    market_type_code: str,
    market_betting_type: str,
    market_limit: int,
    from_datetime: Optional[datetime] = None,
    to_datetime: Optional[datetime] = None,
    sort='FIRST_TO_START',
) -> List[MarketCatalogue]:

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
        market_start_time={
            'from': bf_dt(from_datetime) if from_datetime else None,
            'to': bf_dt(to_datetime) if to_datetime else None,
        }
    )

    # get market catalogues
    return trading.betting.list_market_catalogue(
        filter=race_filter,
        market_projection=market_projection,
        max_results=market_limit,
        sort=sort
    )


default_catalogue_attrs = {
    'market ID': 'market_id',
    'market name': 'market_name',
    'event type ID': 'event_type.id',
    'event type name': 'event_type.name',
    'event ID': 'event.id',
    'event country': 'event.country_code',
    'event name': 'event.name',
    'start time': 'market_start_time',
}


def bf_catalogues_to_df(market_catalogues: List[MarketCatalogue], attrs: Optional[Dict] = None) -> pd.DataFrame:
    if attrs is None:
        attrs = default_catalogue_attrs

    data = [
        {
            k: dgetattr(cat, v)
            for k, v in attrs.items()
        }
        for cat in market_catalogues
    ]
    return pd.DataFrame(data)
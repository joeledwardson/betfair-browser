import json
import os
from collections import deque
from datetime import timedelta, datetime
from os import path
from typing import Optional, Dict
import logging
import pytz
from flumine.markets.market import Market, MarketBook, MarketCatalogue
from ..process import oc
from ..utils import bettingdb

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class UserDataBase:
    """base class for retrieving user recorded data on a market"""
    def __init__(self, db: bettingdb.BettingDB, oc_td: timedelta):
        self._db = db
        self._oc_td = oc_td

    def _p_cache(self, market_id) -> str:
        return self._db.path_mkt_usr_updates(market_id)

    def get_user_data(self, market: Market, market_book: MarketBook) -> Optional[Dict]:
        raise NotImplementedError


class UserDataLoader(UserDataBase):
    """load historic recorded user data from database cache"""
    def __init__(self, db: bettingdb.BettingDB, oc_td: timedelta):
        super().__init__(db, oc_td)
        active_logger.warning(f'timedelta passed to user data loader "{oc_td}" has no effect in historic mode')
        self._usr_mkt_data = dict()

    def get_user_data(self, market: Market, market_book: MarketBook) -> Optional[Dict]:
        if market.market_id not in self._usr_mkt_data:
            p = self._p_cache(market.market_id)
            self._usr_mkt_data[market.market_id] = deque()
            if not (path.exists(p) and path.isfile(p)):
                active_logger.warning(f'market "{market.market_id}", path "{p}" does not exist')
            else:
                with open(p, 'r') as f:
                    for line in f:
                        entry = json.loads(line)
                        if 'timestamp' or 'user_update' not in entry:
                            active_logger.warning(f'"timestamp" or "user_data" not in user data entry')
                        else:
                            entry['timestamp'] = datetime.fromisoformat(entry['timestamp'])
                            self._usr_mkt_data[market.market_id].append(entry)
        dq = self._usr_mkt_data[market.market_id]
        if len(dq):
            if market_book.publish_time >= dq[0]['timestamp']:
                return dq.popleft()['user_update']
        return None


class UserDataStreamer(UserDataBase):
    """stream user data and record"""
    def __init__(self, db: bettingdb.BettingDB, oc_td: timedelta):
        super().__init__(db, oc_td)
        self._oc_mkts = list()
        self._ldn = pytz.timezone('Europe/London')

    def _write_data(self, data: Dict, market_id: str, dt: datetime):
        p = self._p_cache(market_id)
        active_logger.info(f'writing user data to: "{p}"')
        d, _ = path.split(p)
        os.makedirs(d, exist_ok=True)
        update = json.dumps({
            'timestamp': dt.timestamp(),
            'user_update': data
        }) + '\n'
        with open(p, 'a') as f:
            f.write(update)

    def _get_oc_data(self, market: Market, market_book: MarketBook) -> Optional[Dict]:
        if market.market_id in self._oc_mkts:
            return None  # exit if already processed

        if market.market_type != 'WIN':
            active_logger.warning(f'market: "{market.market_id}", currently oddschecker only handles win markets')
            self._oc_mkts.append(market.market_id)
            return None

        now_utc = datetime.utcnow() # naive UTC datetime
        mkt_utc = market_book.market_definition.market_time
        if (mkt_utc - now_utc) > self._oc_td:
            return None

        active_logger.info(f'UTC time now "{now_utc}" within {self._oc_td} of start time {mkt_utc}')
        cat: MarketCatalogue = market.market_catalogue
        if cat is None:
            active_logger.warning(f'market "{market.market_id}" within "{self._oc_td}" of start but no catalogue')
            self._oc_mkts.append(market.market_id)
            return None

        mkt_local = mkt_utc.replace(tzinfo=pytz.utc).astimezone(self._ldn)  # convert UTC market to local time
        url = oc.oc_url(cat.event_type.name, mkt_local, cat.event.venue)
        oc_data = None
        try:
            raw_data = oc.oc(url)
            names = {r.selection_id: r.runner_name for r in cat.runners}
            oc_data = oc.convert_names(raw_data, names)
            self._write_data({'oddschecker': oc_data}, market.market_id, market_book.publish_time)
        except oc.OCException as e:
            active_logger.warning(f'failed to retrieve oddschecker url: "{url}"\n{e}')
        self._oc_mkts.append(market.market_id)
        return oc_data

    def get_user_data(self, market: Market, market_book: MarketBook) -> Optional[Dict]:
        oc_data = self._get_oc_data(market, market_book)
        if oc_data:
            return {'oddschecker_data': oc_data}
        else:
            return None
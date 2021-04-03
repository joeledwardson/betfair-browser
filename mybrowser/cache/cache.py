import logging
from os import path, makedirs
from typing import Optional, List
import zlib
from sqlalchemy.exc import SQLAlchemyError
from betfairlightweight.exceptions import BetfairError
from flumine.exceptions import FlumineException
from mytrading.utils import storage

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def path_market_cache(market_id):
    return path.abspath(path.join('marketcache', market_id))


def write_market_cache(market_id, db) -> bool:
    p = path_market_cache(market_id)
    d, _ = path.split(p)
    if not path.isdir(d):
        makedirs(d)
    active_logger.info(f'writing market cache file:\n-> {p}')

    if path.isfile(p):
        active_logger.info(f'file already exists, exiting...')
        return True

    try:
        r = db.session.query(
            db.tables['marketstream'].columns['data']
        ).filter(
            db.tables['marketstream'].columns['market_id'] == market_id
        ).first()
    except SQLAlchemyError as e:
        active_logger.warning(f'failed to write market file\n{e}', exc_info=True)
        return False

    data = zlib.decompress(r[0]).decode()
    with open(p, 'w') as f:
        f.write(data)
        active_logger.info(f'successfully wrote market file')
    return True


def read_market_cache(market_id, trading) -> Optional[List]:
    p = path_market_cache(market_id)
    active_logger.info(f'reading market cache file:\n-> {p}')

    if not path.isfile(p):
        active_logger.warning(f'file does not exist')
        return None

    try:
        q = storage.get_historical(trading, p)
    except (FlumineException, BetfairError) as e:
        active_logger.warning(f'failed to read market file\n{e}', exc_info=True)
        return None

    l = list(q.queue)
    if not len(l):
        active_logger.warning(f'market cache file is empty')
        return None

    return l


def path_strategy_cache(strategy_id, market_id):
    return path.abspath(path.join('strategycache', strategy_id, market_id))


def write_strategy_cache(strategy_id, market_id, db) -> bool:
    p = path_strategy_cache(strategy_id, market_id)
    d, _ = path.split(p)
    active_logger.info(f'writing strategy market file:\n-> {p}')

    if path.isfile(p):
        active_logger.info(f'file already exists, exiting...')
        return True

    makedirs(d, exist_ok=True)

    try:
        su = db.tables['strategyupdates']
        encoded = db.session.query(
            su.columns['updates']
        ).filter(
            su.columns['strategy_id'] == strategy_id,
            su.columns['market_id'] == market_id
        ).first()

    except SQLAlchemyError as e:
        active_logger.info(f'failed to retrieve info from database\n{e}', exc_info=True)
        return False

    decoded = encoded[0].decode()
    with open(p, 'w') as f:
        f.write(decoded)
    return True


def read_strategy_cache(strategy_id, market_id):
    p = path_strategy_cache(strategy_id, market_id)
    active_logger.info(f'reading strategy market file:\n-> {p}')
    if not path.isfile(p):
        active_logger.warning(f'file does not exist')
        return None

    with open(p) as f:
        return f.read()


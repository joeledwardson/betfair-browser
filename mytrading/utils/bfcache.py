from os import path
from typing import Optional, List
import logging
from betfairlightweight import BetfairError
from betfairlightweight.resources import MarketBook
from flumine import FlumineException

from mytrading.utils import storage
from myutils import dbcache as cache


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def w_mkt(market_id, db, root):
    """
    write market stream cache
    """
    return cache.write_cache_path(
        root=root,
        tbl='marketstream',
        filters={
            'market_id': market_id
        },
        col='data',
        db=db,
        pre_processor=cache.cache_decompress
    )


def p_mkt(market_id, root):
    """
    market stream cache path
    """
    return cache.cache_path(
        root=root,
        tbl='marketstream',
        filters={
            'market_id': market_id
        },
        col='data'
    )


def w_strat(strategy_id, market_id, db, root):
    """
    write strategy updates cache
    """
    return cache.write_cache_path(
        root=root,
        tbl='strategyupdates',
        filters={
            'strategy_id': strategy_id,
            'market_id': market_id
        },
        col='updates',
        db=db,
        pre_processor=cache.cache_decode
    )


def p_strat(strategy_id, market_id, root):
    """
    strategy updates cache path
    """
    return cache.cache_path(
        root=root,
        tbl='strategyupdates',
        filters={
            'strategy_id': strategy_id,
            'market_id': market_id
        },
        col='updates'
    )


def r_mkt(p, trading) -> Optional[List[List[MarketBook]]]:
    """
    read streamed market from cache file, return None on fail
    """

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
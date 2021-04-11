from .config import config
from myutils import dbcache as cache


def _root():
    return config['CONFIG_PATHS']['cache']

# TODO - add read market cache etc here too, would seem the sensible place?
def w_mkt(market_id, db):
    return cache.write_cache_path(
        root=_root(),
        tbl='marketstream',
        filters={
            'market_id': market_id
        },
        col='data',
        db=db,
        pre_processor=cache.cache_decompress
    )


def p_mkt(market_id):
    return cache.cache_path(
        root=_root(),
        tbl='marketstream',
        filters={
            'market_id': market_id
        },
        col='data'
    )


def w_strat(strategy_id, market_id, db):
    return cache.write_cache_path(
        root=_root(),
        tbl='strategyupdates',
        filters={
            'strategy_id': strategy_id,
            'market_id': market_id
        },
        col='updates',
        db=db,
        pre_processor=cache.cache_decode
    )


def p_strat(strategy_id, market_id):
    return cache.cache_path(
        root=_root(),
        tbl='strategyupdates',
        filters={
            'strategy_id': strategy_id,
            'market_id': market_id
        },
        col='updates'
    )

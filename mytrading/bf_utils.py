from flumine import BaseStrategy
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue, RunnerBookEX
from betfairlightweight import APIClient

import json
from mytrading import betting
import os
import pandas as pd
import logging
from typing import List
import operator
from typing import Dict, Callable

SUBDIR_STREAM = 'bf_stream'
SUBDIR_CATALOGUE = 'bf_catalogue'
SUBDIR_OC = 'oddschecker'
OC_EXCHANGES = ['BF', 'MK', 'MA', 'BD', 'BQ']


active_logger = logging.getLogger(__name__)

"""
Use True to return dictionary getter, False to return attribute getter

betfairlightweight RunnerBookEx ojects available_to_back, available_to_lay, traded_volume are inconsistent in 
appearing as lists of dicts with 'price' and 'size', and lists of PriceSize objects.
"""
GETTER = {
    True: dict.get,
    False: getattr
}


class BfUtilsException(Exception):
    pass


def select_operator_side(side, invert=False) -> Callable:
    """
    generic operator selection when comparing odds
    - if side is 'BACK', returns gt (greater than)
    - if side is 'LAY', returns lt (less than)
    - set invert=True to return the other operator
    """
    if side == 'BACK':
        greater_than = True
    elif side == 'LAY':
        greater_than = False
    else:
        raise BfUtilsException(f'side "{side}" not recognised')

    if invert:
        greater_than = not greater_than

    if greater_than:
        return operator.gt
    else:
        return operator.lt


def select_ladder_side(book_ex: RunnerBookEX, side) -> List[Dict]:
    """
    get selected side of runner book ex:
    - if side is 'BACK', returns 'book_ex.available_to_back'
    - if side is 'LAY', returns 'book.ex.available_to_lay'
    """
    if side == 'BACK':
        return book_ex.available_to_back
    elif side == 'LAY':
        return book_ex.available_to_lay
    else:
        raise BfUtilsException(f'side "{side}" not recognised')


def invert_side(side: str) -> str:
    """
    convert 'BACK' to 'LAY' and vice-versa
    """
    if side == 'BACK':
        return 'LAY'
    elif side == 'LAY':
        return 'BACK'
    else:
        raise BfUtilsException(f'side "{side}" not recognised')


def runner_spread(book_ex: RunnerBookEX) -> float:
    """
    get the number of ticks spread between the back and lay side of a runner book
    returns 1000 if either side is empty
    """
    if book_ex.available_to_back and book_ex.available_to_back[0]['price'] in betting.LTICKS_DECODED and \
        book_ex.available_to_lay and book_ex.available_to_lay[0]['price'] in betting.LTICKS_DECODED:

        return betting.LTICKS_DECODED.index(book_ex.available_to_lay[0]['price']) - \
               betting.LTICKS_DECODED.index(book_ex.available_to_back[0]['price'])

    else:

        return len(betting.LTICKS_DECODED)


def get_hist_cat(catalogue_path) -> MarketCatalogue:
    """Get betfair catalogue file"""
    try:
        with open(catalogue_path) as f:
            dat = f.read()
        cat = json.loads(dat)
        return MarketCatalogue(**cat)
    except Exception as e:
        active_logger.warning(f'error getting catalogue "{e}"', exc_info=True)
        return None


def get_hist_stream_data(trading: APIClient, stream_path: str) -> List[List[MarketBook]]:
    """Get historical betfair stream data"""

    stream_logger = logging.getLogger('betfairlightweight.streaming.stream')
    level = stream_logger.level

    if not os.path.isfile(stream_path):

        logging.warning(f'stream path "{stream_path}" does not exist')
        return None

    else:

        try:

            # stop it winging about stream latency
            stream_logger.setLevel(logging.CRITICAL)
            q = betting.get_historical(trading, stream_path)
            # reset level
            stream_logger.setLevel(level)
            return list(q.queue)

        except Exception as e:

            stream_logger.setLevel(level)
            logging.warning(f'error getting historical: "{e}"', exc_info=True)
            return None


def sort_oc(df: pd.DataFrame) -> pd.DataFrame:
    """sort oddschecker dataframe by average value"""

    # get means across columns
    avgs = df.mean(axis=1)
    return avgs.sort_values()


def get_hist_oc_df(oc_path) -> pd.DataFrame:
    """get historical oddschecker file"""
    try:
        return pd.read_pickle(oc_path)
    except Exception as e:
        active_logger.warning(f'error getting oc file: "{e}"', exc_info=True)
        return None


def process_oc_df(df: pd.DataFrame, name_id_map):
    """
    strip exchanges from oddschecker odds dataframe columns and dataframe index (names) with selection IDs on fail,
    will log an error and return None
    """

    df = df[[col for col in df.columns if col not in OC_EXCHANGES]]
    oc_ids = betting.names_to_id(df.index, name_id_map)
    if not oc_ids:
        return None

    df.index = oc_ids
    return df


def oc_hist_mktbk_processor(
        market: Market,
        market_book: MarketBook,
        dir_path,
        name_attr='name'):
    """
    process market book in historical testing, result stored in 'mydat' dict attribute, applied to market object
    function searches for betfair catalogue file and oddschecker dataframe file
    - if processed successfully, mydat['ok'] is True
    """

    d = {
        'ok': False,
    }

    active_logger.info('processing new market "{}" {} {}'.format(
        market_book.market_id,
        market_book.market_definition.market_time,
        market_book.market_definition.event_name
    ))

    # get oddschecker dataframe from file
    oc_df = get_hist_oc_df(os.path.join(
        dir_path,
        SUBDIR_OC,
        market.market_id
    ))
    if oc_df is None:
        return d

    # get betfair category from file
    cat = get_hist_cat(os.path.join(
        dir_path,
        SUBDIR_CATALOGUE,
        market.market_id
    ))
    if cat is None:
        return d

    # process oddschecker dataframe to set with selection IDs
    name_id_map = betting.get_names(cat, name_attr=name_attr, name_key=True)
    oc_df = process_oc_df(oc_df, name_id_map)
    if oc_df is None:
        return d

    # assign results to dict and write as market attribute
    oc_sorted = sort_oc(oc_df)
    d['oc_df'] = oc_df
    d['oc_sorted'] = oc_sorted
    d['id_fav'] = oc_sorted.index[0]
    d['id_outsider'] = oc_sorted.index[-1]
    d['cat'] = cat
    d['ok'] = True
    return d
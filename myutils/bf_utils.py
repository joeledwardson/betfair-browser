from flumine import  BaseStrategy
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue
from betfairlightweight import APIClient

import json
from myutils import betting
import os
import pandas as pd
import logging
from typing import List

SUBDIR_STREAM = 'bf_stream'
SUBDIR_CATALOGUE = 'bf_catalogue'
SUBDIR_OC = 'oddschecker'
OC_EXCHANGES = ['BF', 'MK', 'MA', 'BD', 'BQ']


active_logger = logging.getLogger(__name__)


# sort oddschecker dataframe by average value
def sort_oc(df: pd.DataFrame):
    # get means across columns
    avgs = df.mean(axis=1)
    return avgs.sort_values()


# get historical oddschecker file
def get_hist_oc_df(oc_path):
    try:
        return pd.read_pickle(oc_path)
    except Exception as e:
        active_logger.warning(f'error getting oc file: "{e}"', exc_info=True)
        return None



# strip exchanges from oddschecker odds dataframe columns and dataframe index (names) with selection IDs
# on fail, will log an error and return None
def process_oc_df(df: pd.DataFrame, name_id_map):

    df = df[[col for col in df.columns if col not in OC_EXCHANGES]]
    oc_ids = betting.names_to_id(df.index, name_id_map)
    if not oc_ids:
        return None

    df.index = oc_ids
    return df

# get betfair catalogue file
def get_hist_cat(catalogue_path) -> MarketCatalogue:
    try:
        with open(catalogue_path) as f:
            dat = f.read()
        cat = json.loads(dat)
        return MarketCatalogue(**cat)
    except Exception as e:
        active_logger.warning(f'error getting catalogue "{e}"', exc_info=True)
        return None



# get historical betfair stream data
def get_hist_stream_data(trading: APIClient, stream_path: str) -> List[List[MarketBook]]:

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


# process market book in historical testing, result stored in 'mydat' dict attribute, applied to market object
# function searches for betfair catalogue file and oddschecker dataframe file
# - if processed successfuly, mydat['ok'] is True
def oc_hist_mktbk_processor(
        market: Market,
        market_book: MarketBook,
        dir_path,
        name_attr='name'):

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
"""
functions related to file, storage, path operations when handling betfair files
"""
from queue import Queue
import betfairlightweight
from betfairlightweight.streaming.listener import StreamListener
from datetime import datetime
import sys
from betfairlightweight.resources.bettingresources import MarketBook,  MarketCatalogue
from betfairlightweight import APIClient
import json
from os import path, listdir, walk
import logging
from typing import List
from pathlib import PurePath
import re

SUBDIR_HISTORICAL = 'historical'
SUBDIR_RECORDED = 'recorded'
SUBDIR_STRATEGY_HISTORIC = 'historic_strategies'
SUBDIR_STRATEGY_LIVE = 'live_strategies'

# file extension of order result
EXT_ORDER_RESULT = '.orderresult'
EXT_ORDER_INFO = '.orderinfo'
EXT_CATALOGUE = '.bfcatalogue'
EXT_RECORDED = '.bfrecorded'
EXT_STRATEGY_INFO = '.strategyinfo'
EXT_FEATURE = '.featureinfo'


RE_EVENT = r'^\d{8}$'
RE_MARKET_ID = r'^\d\.\d{9}$'

active_logger = logging.getLogger(__name__)


def get_historical(api_client : APIClient, directory: str) -> Queue:
    """
    Get Queue object from historical Betfair data fil
    e"""

    output_queue = Queue()

    # stop it winging about stream latency by using infinity as max latency
    listener = betfairlightweight.StreamListener(
        output_queue=output_queue,
        max_latency=sys.float_info.max
    )

    stream = api_client.streaming.create_historical_stream(
        file_path=directory,
        listener=listener
    )
    stream.start()

    return output_queue


def get_first_book(file_path: str) -> MarketBook:
    """
    read the first line in a historical/streaming file and get the MarketBook parsed object, without reading or
    processing the rest of the file
    """

    try:
        with open(file_path) as f:
            l = f.readline()
        q = Queue()

        # stop it winging about stream latency by using infinity as max latency
        listener = StreamListener(q, max_latency=sys.float_info.max)
        listener.register_stream(0, 'marketSubscription')
        listener.on_data(l)
        return listener.output_queue.get()[0]
    except Exception as e:
        active_logger.warning(f'error getting first book in file "{file_path}"\n{e}')
        return None


def _construct_hist_dir(event_type_id, event_dt: datetime, event_id, market_id) -> str:
    """
    get path conforming to betfair historical data standards for a given event datetime, event ID, and market ID
    """

    # cant use %d from strftime as it 0-pads and betfair doesnt
    return path.join(
        event_type_id,
        event_dt.strftime('%Y\\%b'),
        str(event_dt.day),
        str(event_id),
        str(market_id)
    )


def construct_hist_dir_cat(catalogue: MarketCatalogue) -> str:
    """
    get path conforming to betfair historical data standards for a given market catalogue
    """
    event_type_id = catalogue.event_type.id
    market_id = catalogue.market_id
    event_id = catalogue.event.id
    event_dt = catalogue.market_start_time

    return _construct_hist_dir(event_type_id, event_dt, event_id, market_id)


def construct_hist_dir(market_book: MarketBook) -> str:
    """
    get path conforming to betfair historical data standards for a given market book
    """
    event_type_id = market_book.market_definition.event_type_id
    market_id = market_book.market_id
    event_id = market_book.market_definition.event_id
    event_dt = market_book.market_definition.market_time

    return _construct_hist_dir(event_type_id, event_dt, event_id, market_id)


def construct_file_hist_dir(file_path: str) -> str:
    """
    get path conforming to betfair historical data standards for a given historical/streaming file path by using
    first book
    """
    bk = get_first_book(file_path)
    if bk:
        return construct_hist_dir(bk)
    else:
        return None


def get_hist_cat(catalogue_path) -> MarketCatalogue:
    """
    Get betfair catalogue file
    """
    try:
        with open(catalogue_path) as f:
            dat = f.read()
        cat = json.loads(dat)
        return MarketCatalogue(**cat)
    except Exception as e:
        active_logger.warning(f'error getting catalogue "{e}"', exc_info=True)
        return None


def get_hist_marketdef(market_path):
    """
    get market definition from historical market, given its file path
    """
    bk = get_first_book(market_path)
    if not bk:
        return None
    else:
        return bk.market_definition


def search_recorded_cat(market_path: str):
    """
    get catalogue from a recorded market, given its directory path
    """
    sub_dir_files = listdir(market_path)
    for f in sub_dir_files:
        if path.splitext(f)[1] == EXT_CATALOGUE:
            cat_path = path.join(market_path, f)
            return get_hist_cat(cat_path)
    return None


def search_recorded_stream(api_client: APIClient, market_path: str):
    """
    get recorded stream market, given its directory path
    """
    sub_dir_files = listdir(market_path)
    for f in sub_dir_files:
        if path.splitext(f)[1] == EXT_RECORDED:
            rec_path = path.join(market_path, f)
            return get_historical(api_client, rec_path)
    return None


def is_orders_dir(files: List[str]) -> bool:
    """
    indicate if directory holds order information and order result files
    """
    file_exts = [path.splitext(f)[1] for f in files]
    return EXT_ORDER_INFO in file_exts or EXT_ORDER_RESULT in file_exts


def strategy_rel_path(strategy_path: str) -> str:
    """
    get relative path for sub-directory/file to root strategy directory, return blank string on fai
    l"""

    p = PurePath(strategy_path)
    if SUBDIR_STRATEGY_HISTORIC in p.parts:
        root_index = p.parts.index(SUBDIR_STRATEGY_HISTORIC)
    elif SUBDIR_STRATEGY_LIVE in p.parts:
        root_index = p.parts.index(SUBDIR_STRATEGY_LIVE)
    else:
        return ''

    # starting from the lowest dir, subtract to get to strategy base directory, then further 3 for strategy root dir,
    # strategy name and strategy timestamp
    parent_index = len(p.parents) - root_index - 3
    if parent_index >= 0:
        base_dir = p.parents[parent_index]
        return path.relpath(strategy_path, base_dir)
    else:
        return ''


def strategy_path_to_hist(strategy_path: str, historic_base_dir: str) -> str:
    """
    convert a market directory contained with a strategies dir to corresponding historic market dir if exists,
    otherwise return blank string
    """
    rel_path = strategy_rel_path(strategy_path)
    if rel_path:
        hist_path = path.join(historic_base_dir, rel_path)
        if path.exists(hist_path):
            return hist_path
    return ''


def strategy_path_convert(strategy_path: str, base_dir: str) -> str:
    """
    convert a path within a strategy to either historical path or recorded path
    """
    return (
            strategy_path_to_hist(strategy_path, path.join(base_dir, SUBDIR_HISTORICAL)) or
            strategy_path_to_hist(strategy_path, path.join(base_dir, SUBDIR_RECORDED))
    )


def get_historical_markets(input_path: str, market_type: str, base_dir: str) -> List[str]:
    """
    get list of historical markets from input path
    """

    if not path.isdir(input_path):
        active_logger.critical(f'input path "{input_path}", assuming market file')
        _markets = [input_path]
    else:
        active_logger.info(f'filtering to market type: "{market_type}"')
        active_logger.info(f'using base dir for strategy: "{base_dir}')
        active_logger.info('\n')

        _markets = []
        for root, dirs, files in walk(input_path):

            for f in files:
                get = False
                _, file_ext = path.splitext(f)
                if re.match(RE_MARKET_ID, f):
                    get = True
                elif re.match(EXT_RECORDED, file_ext):
                    get = True

                if get:
                    file_path = path.join(root, f)
                    market_definition = get_hist_marketdef(file_path)
                    if market_definition is not None:
                        if market_definition.market_type == market_type:
                            _markets.append(file_path)
                            active_logger.info(f'adding market {len(_markets):4} from file "{file_path}')
    return _markets
"""
functions related to file, storage, path operations when handling betfair files
"""
from queue import Queue
import betfairlightweight
from betfairlightweight.streaming.listener import StreamListener
from datetime import datetime
import sys
from betfairlightweight.resources.bettingresources import MarketBook,  MarketCatalogue
from betfairlightweight.resources.streamingresources import MarketDefinition
from betfairlightweight import APIClient
import json
from os import path, listdir, walk
import logging
from typing import List, Optional
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


def get_historical(api_client: APIClient, directory: str) -> Queue:
    """Get Queue object from historical Betfair data file"""
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


def get_first_book(file_path: str) -> Optional[MarketBook]:
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


def get_hist_cat(catalogue_path) -> Optional[MarketCatalogue]:
    """
    Get betfair catalogue file
    """
    try:
        with open(catalogue_path) as f:
            dat = f.read()
        if not dat:
            active_logger.warning(f'catalogue file "{catalogue_path}" is empty')
            return None

        cat = json.loads(dat)
        if not cat:
            active_logger.warning(f'catalogue file "{catalogue_path}" has empty dict')
            return None

        return MarketCatalogue(**cat)

    except Exception as e:
        active_logger.warning(f'error getting catalogue "{e}"', exc_info=True)
        return None


def get_hist_marketdef(market_path) -> Optional[MarketDefinition]:
    """
    get market definition from historical market, given its file path
    """
    bk = get_first_book(market_path)
    if not bk:
        return None
    else:
        return bk.market_definition


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
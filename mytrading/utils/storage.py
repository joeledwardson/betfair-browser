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
import os
import logging
from typing import List


SUBDIR_STREAM = 'bf_stream'
SUBDIR_CATALOGUE = 'bf_catalogue'


active_logger = logging.getLogger(__name__)


def get_historical(api_client : APIClient, directory: str) -> Queue:
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


def file_first_book(file_path: str) -> MarketBook:
    """read the first line in a historical/streaming file and get the MarketBook parsed object, without reading or
    processing the rest of the file"""

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
    """get path conforming to betfair historical data standards for a given event datetime, event ID, and market ID"""

    # cant use %d from strftime as it 0-pads and betfair doesnt
    return os.path.join(
        event_type_id,
        event_dt.strftime('%Y\\%b'),
        str(event_dt.day),
        str(event_id),
        str(market_id)
    )


def construct_hist_dir(market_book: MarketBook) -> str:
    """get path conforming to betfair historical data standards for a given market book"""
    event_type_id = market_book.market_definition.event_type_id
    market_id = market_book.market_id
    event_id = market_book.market_definition.event_id
    event_dt = market_book.market_definition.market_time

    return _construct_hist_dir(event_type_id, event_dt, event_id, market_id)


def construct_file_hist_dir(file_path: str) -> str:
    """get path conforming to betfair historical data standards for a given historical/streaming file path"""
    bk = file_first_book(file_path)
    if bk:
        return construct_hist_dir(bk)
    else:
        return None


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


import json
from ..utils.storage import _construct_hist_dir, construct_hist_dir, EXT_RECORDED, SUBDIR_RECORDED, EXT_CATALOGUE
from betfairlightweight.resources.bettingresources import MarketBook
from flumine.markets.market import Market
from datetime import timedelta, datetime, timezone
import logging
from typing import Dict, List
from os import path, makedirs
from flumine import BaseStrategy
from dateutil.parser import parse

active_logger = logging.getLogger(__name__)


class MyRecorderStrategy(BaseStrategy):
    """
    Record streaming updates by writing to file

    Would make more sense to use `process_raw_data` but would have to configure a stream from
    `flumine.streams.datastream.FlumineStream` which produces `RawDataEvent`
    However, by default strategies use `flumine.streams.marketstream.MarketStream` which does not use this and I'm
    not sure how to combine the two streams, whereby the `MarketStream` produces `MarketBook` updates but also raw
    data so just going to process from market books


    """

    MARKET_ID_LOOKUP = "id"

    def __init__(self, base_dir, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_dir = base_dir
        self.market_paths = {}
        self.catalogue_paths = {}

    #
    # def process_raw_data(self, publish_time: int, data: dict) -> None:
    #
    #     # get market ID and check valid
    #     market_id = data.get(self.MARKET_ID_LOOKUP, None)
    #     if market_id is None:
    #         active_logger.error(f'market ID not found')
    #         return
    #
    #     # check if market is tracked yet
    #     if market_id not in self.market_paths:
    #
    #         try:
    #             # get market information from market definition
    #             md = data['marketDefinition']
    #             event_type_id = md['eventTypeId']
    #             event_dt = parse(md['marketTime'])
    #             event_id = md['eventId']
    #
    #             # create directory for historical market using its meta info on event type/date/market ID
    #             dir_path = path.join(
    #                 self.base_dir,
    #                 SUBDIR_RECORDED,
    #                 _construct_hist_dir(event_type_id, event_dt, event_id, market_id)
    #             )
    #             makedirs(dir_path, exist_ok=True)
    #
    #             # get path for historical file where market data to be stored
    #             market_path = path.join(
    #                 dir_path,
    #                 market_id + EXT_RECORDED
    #             )
    #             self.market_paths[market_id] = market_path
    #             active_logger.info(f'new market started recording: "{market_id}" to {market_path}')
    #
    #         except Exception as e:
    #             # error getting market recording path, set to None to dict to indicate this
    #             active_logger.error(f'failed to create market path from ID "{market_id}": {e}', exc_info=True)
    #             self.market_paths[market_id] = None
    #
    #     # get historical market file path and check valid
    #     market_path = self.market_paths.get(market_id, None)
    #     if market_path:
    #
    #         # construct data in historical format
    #         update = {
    #             'op': 'mcm',
    #             'clk': None,
    #             'pt': publish_time,
    #             'mc': [data]
    #         }
    #
    #         # convert to string and add newline
    #         update = json.dumps(update) + '\n'
    #
    #         # write to file
    #         with open(self.market_paths[market_id], 'a') as f:
    #             f.write(update)

    def check_market_book(self, market: Market, market_book: MarketBook) -> bool:
        return True

    def process_market_book(self, market: Market, market_book: MarketBook) -> None:
        market_id = market_book.market_id

        if market_id not in self.catalogue_paths and market.market_catalogue:

            # make sure dir exists
            dir_path = path.join(
                self.base_dir,
                SUBDIR_RECORDED,
                construct_hist_dir(market_book)
            )
            makedirs(dir_path, exist_ok=True)

            # store catalogue
            catalogue_path = path.join(
                dir_path,
                market_id + EXT_CATALOGUE
            )
            self.catalogue_paths[market_id] = catalogue_path
            active_logger.info(f'writing market id "{market_id}" catalogue to "{catalogue_path}"')
            with open(catalogue_path, 'w') as file_catalogue:
                file_catalogue.write(market.market_catalogue.json())

        if market_id not in self.market_paths:

            # create directory for historical market
            dir_path = path.join(
                self.base_dir,
                SUBDIR_RECORDED,
                construct_hist_dir(market_book)
            )
            makedirs(dir_path, exist_ok=True)

            # get path for historical file where market data to be stored
            market_path = path.join(
                dir_path,
                market_id + EXT_RECORDED
            )
            self.market_paths[market_id] = market_path
            active_logger.info(f'new market started recording: "{market_id}" to {market_path}')

        # convert datetime to milliseconds since epoch
        pt = int((market_book.publish_time - datetime.utcfromtimestamp(0)).total_seconds() * 1000)

        # construct data in historical format
        update = {
            'op': 'mcm',
            'clk': None,
            'pt': pt,
            'mc': [market_book.streaming_update]
        }

        # convert to string and add newline
        update = json.dumps(update) + '\n'

        # write to file
        with open(self.market_paths[market_id], 'a') as f:
            f.write(update)

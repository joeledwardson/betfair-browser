import json
from ..utils.storage import construct_hist_dir, EXT_RECORDED, SUBDIR_RECORDED
from betfairlightweight.resources.bettingresources import MarketBook
from datetime import timedelta, datetime, timezone
import logging
from typing import Dict, List
from os import path, makedirs
from flumine import BaseStrategy

active_logger = logging.getLogger(__name__)


class MyRecorderStrategy(BaseStrategy):

    def __init__(self, base_dir, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_dir = base_dir
        self.market_paths = {}

    def market_book_processor(self, market_book: MarketBook):

        market_id = market_book.market_id

        if market_id not in self.market_paths:
            dir_path = path.join(
                self.base_dir,
                SUBDIR_RECORDED,
                construct_hist_dir(market_book)
            )
            makedirs(dir_path)
            self.market_paths[market_id] = path.join(
                dir_path,
                market_id + EXT_RECORDED
            )

        # convert datetime to milliseconds since epoch
        pt = int((market_book.publish_time - datetime.utcfromtimestamp(0)).total_seconds() * 1000)

        # construct data in historical format
        update = {
            'op': 'mcm',
            'pt': pt,
            'mc': [market_book.streaming_update]
        }

        # convert to string and add newline
        update = json.dumps(update) + '\n'

        # write to file
        with open(self.market_paths[market_id], 'a') as f:
            f.write(update)

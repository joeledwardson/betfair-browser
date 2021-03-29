from os import walk, path
import re
import logging
from typing import Optional, Dict
from betfairlightweight.resources.streamingresources import MarketDefinition
from betfairlightweight.resources.bettingresources import MarketCatalogue, MarketBook
from mytrading.utils.storage import get_historical, get_first_book, get_hist_cat
from mytrading.utils.storage import RE_MARKET_ID, EXT_CATALOGUE, EXT_RECORDED
from .bettingdb import BettingDB

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def get_meta(first_book: MarketBook, cat: MarketCatalogue = None) -> Dict:
    """
    Get metadata corresponding to the "Meta" table in the betting database for a given betfair Market

    Parameters
    ----------
    first_book : first MarketBook for betfair Market
    cat : if market is recorded and not historic, this needs to be passed to get
    venue and runner names

    Returns dict of metadata
    -------

    """
    mktdef: MarketDefinition = first_book.market_definition
    mktid = first_book.market_id
    init_time = first_book.publish_time
    pre_off = mktdef.market_time - init_time

    metadata = {
        'market_id': mktid,
        'sport_id': mktdef.event_type_id,
        'market_time': mktdef.market_time,
        'market_type': mktdef.market_type,
        'betting_type': mktdef.betting_type,
        'country_code': mktdef.country_code,
        'event_id': mktdef.event_id,
        'event_name': mktdef.event_name,  # historical
        'timezone': mktdef.timezone,
        'venue': mktdef.venue,
        'init_time': init_time,
        'pre_off': pre_off,
        'format': 'historic',
    }

    if cat is not None:
        metadata['event_name'] = cat.event.name
        metadata['venue'] = cat.event.venue
        metadata['format'] = 'recorded'

    return metadata


def market_to_db(db: BettingDB, stream_path: str, cat_path: str = None) -> bool:
    """
    Insert row(s) into database table(s) for Meta and streaming info for a given historic/streaming file and its
    corresponding catalogue (only needed if type is recorded, not historic)

    Parameters
    ----------
    stream_path : path to historic/recorded file
    cat_path : (optional) path to catalogue

    Returns True on success
    -------

    """
    with open(stream_path) as f:
        data = f.read()

    cat = None
    if cat_path:
        cat = get_hist_cat(cat_path)
        if cat is None:
            return False

    bk = get_first_book(stream_path)
    if bk is None:
        return False

    if cat is None:
        names = {
            r.selection_id: r.name
            for r in bk.market_definition.runners
        }
    else:
        names = {
            r.selection_id: r.runner_name
            for r in cat.runners
        }

    meta = get_meta(bk, cat)

    return db.insert_market(data, meta, names, cat)


def dir_to_db(db: BettingDB, dirpath: str) -> None:
    """
    Process a directory recursively, attempting to find historic market file(s) and recorded/catalogue market file
    pair(s) and add them to the betting database

    Parameters
    ----------
    dirpath : directory to search
    -------

    """

    for dirpath, dirnames, filenames in walk(dirpath):
        for filename in filenames:

            filepath = path.join(dirpath, filename)
            file, ext = path.splitext(filepath)

            if re.match(RE_MARKET_ID, filename):
                active_logger.info(f'processing file "{filepath}"')
                market_to_db(db, filepath)

            elif ext == EXT_RECORDED:
                cat_path = file + EXT_CATALOGUE
                active_logger.info(f'processing file "{filepath}"')

                if path.exists(cat_path):
                    market_to_db(db, filepath, cat_path)

                else:
                    active_logger.warning(f'"{filepath}" <- recorded file\n'
                                          f'"{cat_path}" <- catalogue file not found')


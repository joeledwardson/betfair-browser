import os
from os import path
from typing import List, Tuple
import logging
import re
from betfairlightweight import APIClient
from mytrading.utils.storage import SUBDIR_HISTORICAL, SUBDIR_RECORDED
from mytrading.utils.storage import RE_MARKET_ID
from mytrading.utils.storage import get_hist_marketdef, search_recorded_cat, search_recorded_stream
from mytrading.utils.storage import strategy_path_to_hist, get_historical
from mytrading.browser.marketinfo import MarketInfo


def get_market_info(market_path):
    """
    get information about a betfair market from its path
    can be either:
    - path to betfair historical file, whereby filename conforms to market ID
    - directory of recorded market information, where directory conforms to market ID and has catalogue file inside

    :param market_path:
    :return:
    """

    if path.isfile(market_path):
        # assume betfair historical
        market_def = get_hist_marketdef(market_path)
        if market_def:
            return MarketInfo.from_historical(market_def)

    elif path.isdir(market_path):
        # assume recorded
        cat = search_recorded_cat(market_path)
        if cat:
            return MarketInfo.from_catalogue(cat)

    return None


def get_recorded_market(
        market_dir: str,
        trading: APIClient,
        file_info: List[str]
) -> Tuple[bool, List, MarketInfo]:
    """
    try to retrieve a betfair catalogue and recorded files from directory
    return as boolean success, record list and catalogue object
    record list and catalogue object are None on success fail
    """

    cat = search_recorded_cat(market_dir)
    if not cat:
        file_info.append(f'did not find catalogue in dir "{market_dir}"')
        return False, None, None

    market_info = MarketInfo.from_catalogue(cat)
    file_info.append(f'found catalogue file in dir "{market_dir}"')

    queue = search_recorded_stream(trading, market_dir)
    if not queue:
        file_info.append(f'did not find recorded recorded file in "{market_dir}"')
        return False, None, None

    records = list(queue.queue)
    n_records = len(records)
    file_info.append(f'found {n_records} recorded records in "{market_dir}"')

    if n_records == 0:
        file_info.append(f'file empty')
        return False, None, None

    return True, records, market_info


def get_historical_market(
        historical_path: str,
        trading: APIClient,
        file_info: List[str]
) -> Tuple[bool, List, MarketInfo]:
    """
    try to retrieve a betfair historical file processing into record list and market info object
    return as boolean success, record list and market info object
    record list and catalogue object are None on success fail
    """

    try:
        records = list(get_historical(trading, historical_path).queue)
        file_info.append(f'found {len(records)} historical records in "{historical_path}"')

        if len(records):
            market_info = MarketInfo.from_historical(records[-1][0].market_definition)
            return True, records, market_info
        else:
            file_info.append('file empty')
            return False, None, None

    except Exception as exp:
        file_info.append(f'Error getting records from "{historical_path}"\n{exp}')
        logging.warning(f'Error getting records from "{historical_path}"', exc_info=True)
        return False, None, None


def get_orders_market(
        dir_path: str,
        base_dir: str,
        trading: APIClient,
        file_info: List[str]
) -> Tuple[bool, List, MarketInfo]:
    """
    assuming for a strategy market directory containing orders, try to use relative path from base directory in
    either historical or recorded sub-directories to retrieve records and market information
    """

    # get historic file path relative to current orders directory
    hist_path = strategy_path_to_hist(
        strategy_path=dir_path,
        historic_base_dir=path.join(base_dir, SUBDIR_HISTORICAL))

    # check that file name corresponds to market ID
    name_is_market = re.match(RE_MARKET_ID, path.split(hist_path)[1])

    # historic path exists, is a file and name matches market ID
    if hist_path and path.isfile(hist_path) and name_is_market:
        file_info.append(f'found historical path at "{hist_path}"')
        return get_historical_market(hist_path, trading, file_info)

    # get recorded directory path relative to current orders directory
    rec_path = strategy_path_to_hist(
        strategy_path=dir_path,
        historic_base_dir=path.join(base_dir, SUBDIR_RECORDED))

    # check that directory corresponds to market ID
    dir_is_market = re.match(RE_MARKET_ID, path.split(rec_path)[1])

    # recorded path exists, is a directory and matches market ID
    if rec_path and path.isdir(rec_path) and dir_is_market:
        file_info.append(f'found recorded path at "{rec_path}"')
        return get_recorded_market(rec_path, trading, file_info)

    file_info.append('failed to find historic or recorded path to match')
    return False, None, None


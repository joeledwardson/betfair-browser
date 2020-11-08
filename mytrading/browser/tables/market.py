import logging
import re
from os import path
from typing import List, Tuple

import dash_table
from betfairlightweight import APIClient

from ...utils.storage import is_orders_dir, get_historical, search_recorded_cat, search_recorded_stream
from ...utils.storage import strategy_path_to_hist
from ...utils.storage import SUBDIR_HISTORICAL, RE_MARKET_ID, SUBDIR_RECORDED
from ..filetracker import FileTracker
from ..marketinfo import MarketInfo
from ..tables.files import get_hist_cell_path



def get_market_table(
        height,
        width
) -> dash_table.DataTable:
    """
    get empty dash DataTable for runner information
    """
    return dash_table.DataTable(
        id='table-market',
        columns=[{
            'name': x,
            'id': x
        } for x in ['Attribute', 'Value']],
        fixed_rows={
            'headers': True
        },
        style_table={
            'height': height,
            'width': width,
        },
        style_cell={
            'textAlign': 'left'
        },
    )


def get_records_market(
        file_tracker: FileTracker,
        trading: APIClient,
        base_dir: str,
        file_info: List[str],
        active_cell
) -> Tuple[bool, List, MarketInfo]:
    """
    get [success, records, marketinfo] from a directory indicated by `file_tracker`

    - if path is historic file, use to get records and market information
    - if path directory contains catalogue and recorded data, use to get records and market information
    - if path directory holds order information,

    Parameters
    ----------
    file_tracker :
    trading :
    base_dir :
    file_info :
    active_cell :

    Returns
    -------
    [success, records, marketinfo]

    """

    # try to look if there are orders inside directory
    if is_orders_dir(file_tracker.files):

        # orders inside directory, get success, records, marketinfo from corresponding historic/recorded
        file_info.append(f'found order result/info files in "{file_tracker.root}"')
        return get_orders_market(
            file_tracker.root,
            base_dir,
            trading,
            file_info
        )

    # get file path from selected cell file files table
    hist_path = get_hist_cell_path(file_tracker, active_cell, file_info)

    # check if file selected valid
    if hist_path:

        # try and get
        return get_historical_market(hist_path, trading, file_info)

    # try to use directory to get recorded/catalogue market data
    return get_recorded_market(file_tracker.root, trading, file_info)


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
            market_info = MarketInfo.from_historical(records[-1][0].market_definition, records[0][0])
            return True, records, market_info
        else:
            file_info.append('file empty')
            return False, None, None

    except Exception as exp:
        file_info.append(f'Error getting records from "{historical_path}"\n{exp}')
        logging.warning(f'Error getting records from "{historical_path}"', exc_info=True)
        return False, None, None


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
        historic_base_dir=path.join(base_dir, SUBDIR_HISTORICAL)
    )

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

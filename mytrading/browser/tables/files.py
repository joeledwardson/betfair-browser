import re
from os import path
from typing import List
import dash_table
import pandas as pd

from ...utils.storage import RE_EVENT, EXT_ORDER_RESULT, RE_MARKET_ID, EXT_FEATURE
from ...utils.storage import get_hist_marketdef, get_first_book, search_recorded_cat
from myutils.mypath import walk_first
from ...utils.storage import strategy_rel_path, strategy_path_convert, is_orders_dir
from ..filetracker import FileTracker
from ..marketinfo import MarketInfo
from ..profit import get_display_profits
from .table import create_table


def get_display_info(
        base_dir: str,
        dir_path: str,
        elements: List[str]
) -> List[str]:
    """
    get information to display next to each file/directory
    - if dir is an event, display event name
    - if dir is a market, display market information
    """

    # list of file/dir info to display
    display_info = []

    # check if directory has order results - if so market information for parent needed
    order_market_info: MarketInfo = None

    # see if directory has orders
    if is_orders_dir(elements):

        # try to convert directory to recorded/historical directory for relevant market
        order_market_path = strategy_path_convert(dir_path, base_dir)

        # if successful in getting recorded/historical directory for market, get market information
        if order_market_path:
            order_market_info = get_market_info(order_market_path)

    # loop dirs/files elements
    for e in elements:

        # create empty string for display information
        info = ''

        # construct full path of element with parent directory
        element_path = path.join(dir_path, e)

        # get file extension
        file_ext = path.splitext(e)[1]

        # check if element is directory and matches betfair event
        if re.match(RE_EVENT, e) and path.isdir(element_path):
            event_path = element_path

            # if active directory in strategy, then attempt to convert path to its historical/recorded counterpart
            if strategy_rel_path(event_path):
                event_path = strategy_path_convert(event_path, base_dir)

            # set information string as event info
            info = get_event_dir_info(event_path)

        # check if element is a market ID (can be file in historical or dir in recorded), get market information
        elif re.match(RE_MARKET_ID, e):
            market_path = element_path

            # if active path in strategy, then attempt to convert path to its historical/recorded counterpart
            if strategy_rel_path(market_path):
                market_path = strategy_path_convert(market_path, base_dir)

            # set information string as market info
            info = get_market_info(market_path)

            # use blank string if function returned None otherwise convert MarketInfo object to string
            info = str(info) if info else ''

        # check if element is strategy order result or feature info
        elif file_ext in [EXT_ORDER_RESULT, EXT_FEATURE]:

            # check that were able to get relevant market information
            if order_market_info is not None:

                # use file name excluding extension for selection ID
                selection_id = path.splitext(e)[0]

                try:

                    # convert file name string to int
                    selection_id = int(selection_id)

                    # set information string as selection name
                    info = order_market_info.names.get(selection_id, '')

                except ValueError:

                    # string empty etc
                    pass

        display_info.append(info)

    return display_info


def get_files_table(
        ft: FileTracker,
        base_dir: str,
        do_profits=False,
        active_cell=None,
        table_id='table-files',
) -> dash_table.DataTable:
    """
    get filled dash datatable displaying list of dirs, files and relevant information
    """

    # get list of display strings for dir/files elements
    display_info = get_display_info(
        base_dir,
        ft.root,
        ft.elements
    )

    # check if get profits is specified
    if do_profits:

        # get profits from order result elements
        profits = get_display_profits(
            ft.root,
            ft.elements
        )

    else:

        # use blank strings for profit column
        profits = [''] * len(ft.elements)

    df = pd.DataFrame({
        'Name': ft.display_list,
        'Info': display_info,
        'Profit': profits
    })

    return create_table(
        table_id=table_id,
        df=df,
        active_cell=active_cell,
    )


def get_hist_cell_path(
        file_tracker: FileTracker,
        active_cell,
        file_info: List[str]
) -> str:
    """
    get path of betfair historic file based on row of active cell in table, return blank string on fail
    """

    if not active_cell:
        file_info.append('no active cell in files table')
        return ''

    if 'row' not in active_cell:
        file_info.append(f'No "row" attribute in active cell: {active_cell}')
        return ''

    row = active_cell['row']
    if not len(file_tracker.dirs) <= row < len(file_tracker.display_list):
        file_info.append(f'Row {row}, is not a valid file selection')
        return ''

    file_name = file_tracker.get_file_name(row)

    if not re.match(RE_MARKET_ID, file_name):
        file_info.append(f'active cell file "{file_name}" does not match market ID')
        return ''

    return path.join(file_tracker.root, file_name)


def get_market_info(market_path):
    """
    get information about a betfair market from its path
    can be either:
    - path to betfair historical file, whereby filename conforms to market ID
    - directory of recorded market information, where directory conforms to market ID and has catalogue file inside

    :param market_path:
    :return:
    """

    # check if file
    if path.isfile(market_path):

        # assume betfair historical and get market definition
        market_def = get_hist_marketdef(market_path)

        # get first market book
        first_book = get_first_book(market_path)

        # check if both first book and market definition valid
        if market_def and first_book:
            return MarketInfo.from_historical(market_def, first_book)

    # check if directory
    elif path.isdir(market_path):

        # assume recorded market directory and search for catalogue
        cat = search_recorded_cat(market_path)

        # check if successful getting catalogue
        if cat:
            return MarketInfo.from_catalogue(cat)

    return None


def get_event_dir_info(dir_path) -> str:
    """
    get event information string containing venue from a directory path
    directory path can be either:
    - betfair historical event dir path containing market files, where event info contained in files
    - recorded event dir, where market dirs hold catalogue file for event info

    on failure to extract info from both above, returns empty string
    """

    # get sub directories and files
    _, dirs, files = walk_first(dir_path)

    # loop files
    for f in files:

        # if historical, market ID is name
        if re.match(RE_MARKET_ID, f):

            # get market definition from file
            market_def = get_hist_marketdef(path.join(dir_path, f))

            # if successful, return event name from market definition
            if market_def:
                return market_def.event_name

    # loop directories
    for d in dirs:

        # if recorded, event dir holds dirs named using market IDs
        if re.match(RE_MARKET_ID, d):

            # form sub-directory path of market
            sub_dir_path = path.join(dir_path, d)

            # search for catalogue in market directory
            cat = search_recorded_cat(sub_dir_path)

            # if successfully found catalogue, then return event name from it
            if cat:
                return cat.event.name

    return ''

import re
from itertools import chain
from os import path
from typing import Iterable, List, Tuple
import dash_html_components as html
import dash_table
import pandas as pd

from mytrading.browser.tables.table import create_table
from mytrading.browser.data import DashData
from mytrading.browser.event import get_event_dir_info
from mytrading.browser.filetracker import FileTracker
from mytrading.browser.market import get_market_info, get_orders_market, get_historical_market, get_recorded_market
from mytrading.browser.marketinfo import MarketInfo
from mytrading.browser.profit import get_profits
from mytrading.utils.storage import RE_EVENT, EXT_ORDER_RESULT, RE_MARKET_ID
from mytrading.utils.storage import strategy_rel_path, strategy_path_convert, is_orders_dir


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

    # check if directory has order results - if so, try to get market information so can use get selection names for
    # elements
    order_market_info: MarketInfo = None
    if is_orders_dir(elements):
        order_market_path = strategy_path_convert(dir_path, base_dir)
        if order_market_path:
            order_market_info = get_market_info(order_market_path)

    for e in elements:
        info = ''
        element_path = path.join(dir_path, e)

        # if element is directory and matches betfair event, get event information
        if re.match(RE_EVENT, e) and path.isdir(element_path):
            event_path = element_path

            # if active directory in strategy, then attempt to convert path to its historical/recorded counterpart
            if strategy_rel_path(event_path):
                event_path = strategy_path_convert(event_path, base_dir)

            info = get_event_dir_info(event_path)

        # if element is a market ID (can be file in historical or dir in recorded), get market information
        elif re.match(RE_MARKET_ID, e):
            market_path = element_path

            # if active path in strategy, then attempt to convert path to its historical/recorded counterpart
            if strategy_rel_path(market_path):
                market_path = strategy_path_convert(market_path, base_dir)

            info = get_market_info(market_path)

            # use blank string if function returned None otherwise convert MarketInfo object to string
            info = str(info) if info else ''

        # if element is strategy order result, try to get selection name from market info
        elif path.splitext(e)[1] == EXT_ORDER_RESULT:
            if order_market_info is not None:
                selection_id = path.splitext(e)[0]
                try:
                    # convert file name string to int
                    selection_id = int(selection_id)
                    info = order_market_info.names.get(selection_id, '')
                except ValueError:
                    # string empty etc
                    pass

        display_info.append(info)

    return display_info


def get_display_profits(
        dir_path: str,
        elements: Iterable[str]
) -> List[str]:

    display_profits = []
    for e in elements:
        element_path = path.join(dir_path, e)
        profit = get_profits(element_path)
        if profit is not None:
            profit_str = f'£{profit:+.2f}'
        else:
            profit_str = ''
        display_profits.append(profit_str)
    return display_profits


def get_files_table(
        file_tracker: FileTracker,
        base_dir: str,
        do_profits=False,
        active_cell=None,
        table_id='table-files',
) -> dash_table.DataTable:
    """
    get filled mydash datatable displaying list of dirs, files and relevant information
    """

    elements = list(chain(file_tracker.dirs, file_tracker.files))
    display_info = get_display_info(base_dir, file_tracker.root, elements)
    if do_profits:
        profits = get_display_profits(file_tracker.root, elements)
    else:
        profits = [''] * len(elements)

    df = pd.DataFrame({
        'Name': file_tracker.display_list,
        'Info': display_info,
        'Profit': profits
    })

    return create_table(
        table_id=table_id,
        df=df,
        active_cell=active_cell,
    )


def get_hist_cell_path(
        dash_data: DashData,
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
    if not len(dash_data.file_tracker.dirs) <= row < len(dash_data.file_tracker.display_list):
        file_info.append(f'Row {row}, is not a valid file selection')
        return ''

    file_name = dash_data.file_tracker.get_file_name(row)

    if not re.match(RE_MARKET_ID, file_name):
        file_info.append(f'active cell file "{file_name}" does not match market ID')
        return ''

    return path.join(dash_data.file_tracker.root, file_name)


def get_table_market(
        dash_data: DashData,
        base_dir: str,
        file_info: List[str],
        active_cell
) -> Tuple[bool, List, MarketInfo]:
    """
    get market historical records and market information based on file path
    - if path is historic file, use to get records and market information
    - if path directory contains catalogue and recorded data, use to get records and market information
    - if path directory holds order information,
    """

    # try to look if there are orders inside directory
    if is_orders_dir(dash_data.file_tracker.files):
        file_info.append(f'found order result/info files in "{dash_data.file_tracker.root}"')
        return get_orders_market(
            dash_data.file_tracker.root,
            base_dir,
            dash_data.trading,
            file_info)

    # try to get path of historic file from table selected cell
    hist_path = get_hist_cell_path(dash_data, active_cell, file_info)
    if hist_path:
        return get_historical_market(hist_path, dash_data.trading, file_info)

    # try to use directory to get recorded/catalogue market data
    return get_recorded_market(dash_data.file_tracker.root, dash_data.trading, file_info)
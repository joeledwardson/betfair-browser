from os import path, listdir
from typing import Iterable, List

from mytrading.tradetracker import orderinfo
from mytrading.utils import storage
from myutils import jsonfile


def get_profits(element_path):
    """get sum of profits in current directory by recursively adding up profits from .orderresult files"""

    if path.isfile(element_path):
        if path.splitext(element_path)[1] == storage.EXT_ORDER_RESULT:
            lines = jsonfile.read_file_lines(element_path)
            return sum(orderinfo.dict_order_profit(o) for o in lines)
        else:
            return None
    elif path.isdir(element_path):
        elements = listdir(element_path)
        result = 0
        valid = False
        for element_name in elements:
            value = get_profits(path.join(element_path, element_name))
            result += (value or 0)
            valid = True if value is not None or valid is True else False
        return None if not valid else result
    else:
        return None


def display_profit(value) -> str:
    """convert a numerical profit value to signed currency string, or None to blank string"""
    if value is not None:
        return f'£{value:+.2f}'
    else:
        return ''


def get_display_profits(
        dir_path: str,
        elements: Iterable[str]
) -> List[str]:
    """for a list of elements (dirs/files), get the recorded strategy profit in currency form or blank if not found"""

    display_profits = []
    for e in elements:
        element_path = path.join(dir_path, e)
        profit = get_profits(element_path)
        profit_str = display_profit(profit)
        display_profits.append(profit_str)
    return display_profits
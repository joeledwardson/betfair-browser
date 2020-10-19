from betfairlightweight.resources.bettingresources import RunnerBookEX

from mytrading.utils.types import BfUtilsException
import logging
from typing import List
import operator
from typing import Dict, Callable


active_logger = logging.getLogger(__name__)


def select_operator_side(side, invert=False) -> Callable:
    """
    generic operator selection when comparing odds
    - if side is 'BACK', returns gt (greater than)
    - if side is 'LAY', returns lt (less than)
    - set invert=True to return the other operator
    """
    if side == 'BACK':
        greater_than = True
    elif side == 'LAY':
        greater_than = False
    else:
        raise BfUtilsException(f'side "{side}" not recognised')

    if invert:
        greater_than = not greater_than

    if greater_than:
        return operator.gt
    else:
        return operator.lt


def select_ladder_side(book_ex: RunnerBookEX, side) -> List[Dict]:
    """
    get selected side of runner book ex:
    - if side is 'BACK', returns 'book_ex.available_to_back'
    - if side is 'LAY', returns 'book.ex.available_to_lay'
    """
    if side == 'BACK':
        return book_ex.available_to_back
    elif side == 'LAY':
        return book_ex.available_to_lay
    else:
        raise BfUtilsException(f'side "{side}" not recognised')


def invert_side(side: str) -> str:
    """
    convert 'BACK' to 'LAY' and vice-versa
    """
    if side == 'BACK':
        return 'LAY'
    elif side == 'LAY':
        return 'BACK'
    else:
        raise BfUtilsException(f'side "{side}" not recognised')


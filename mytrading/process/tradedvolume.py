from betfairlightweight.resources.bettingresources import PriceSize, RunnerBook, MarketBook
import pandas as pd
import logging
from typing import List, Dict
from .getter import GETTER
from .runner import get_book


active_logger = logging.getLogger(__name__)


def traded_runner_vol(runner: RunnerBook, is_dict=True):
    """Get runner traded volume across all prices"""
    return sum(e['size'] if is_dict else e.size for e in runner.ex.traded_volume)


def total_traded_vol(record: MarketBook):
    """Get traded volume across all runners at all prices"""
    return sum(traded_runner_vol(runner) for runner in record.runners)


def get_record_tv_diff(tv1: List[PriceSize], tv0: List[PriceSize], is_dict=False) -> List[Dict]:
    """
    Get difference between traded volumes from one tv ladder to another
    use is_dict=False if `price` and `size` are object attributes, use is_dict=True if are dict keys
    """
    traded_diffs = []

    atr = GETTER[is_dict]

    # loop items in second traded volume ladder
    for y in tv1:

        # get elements in first traded volume ladder if prices matches
        m = [x for x in tv0 if atr(x, 'price') == atr(y, 'price')]

        # first element that matches
        n = next(iter(m), None)

        # get price difference, using 0 for other value if price doesn't exist
        size_diff = atr(y, 'size') - (atr(n, 'size') if m else 0)

        # only append if there is a difference
        if size_diff:
            traded_diffs.append({
                'price': atr(y, 'price'),
                'size': size_diff
            })

    return traded_diffs


def get_tv_diffs(records, runner_id, is_dict=False) -> pd.DataFrame:
    """
    Get traded volume differences for a selected runner between adjacent records
    DataFrame has record publish time index, 'price' column for odds and 'size' column for difference in sizes
    """

    dts = []
    diffs = []

    for i in range(1, len(records)):
        r1 = records[i][0]
        r0 = records[i - 1][0]

        r0_book = get_book(r0.runners, runner_id)
        r1_book = get_book(r1.runners, runner_id)

        if r0_book and r1_book:
            new_diffs = get_record_tv_diff(r1_book.ex.traded_volume,
                                           r0_book.ex.traded_volume,
                                           is_dict)

            # filter out entries with £0
            new_diffs = [d for d in new_diffs if d['size']]
            diffs += new_diffs
            dts += [r1.publish_time for _ in new_diffs]

    return pd.DataFrame(diffs, index=dts)


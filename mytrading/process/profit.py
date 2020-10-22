from datetime import datetime
import pandas as pd
from flumine.order.order import BetfairOrder
from myutils.jsonfile import read_file
import logging

active_logger = logging.getLogger(__name__)


def order_profit(sts: str, side: str, price: float, size: float) -> float:
    """
    Compute order profit from dictionary of values retrieved from a line of a file written to by TradeTracker.log_update

    Function is shamelessly stolen from `flumine.backtest.simulated.Simulated.profit`, but that requires an order
    instance which is not possible to create trade/strategy information etc
    """

    if sts == "WINNER":
        if side == "BACK":
            return round((price - 1) * size, ndigits=2)
        else:
            return round((price - 1) * -size, ndigits=2)
    elif sts == "LOSER":
        if side == "BACK":
            return -size
        else:
            return size
    else:
        return 0.0

import os
import numpy as np
import pandas as pd
from myutils import generic


def get_tick_increments() -> pd.DataFrame:
    """
    Get list of tick increments in encoded integer format
    Retrieves list of {'Start', 'Stop', 'Step'} objects from JSON file 'ticks.json'
    """

    # generate file path based on current directory and filename "ticks.json"
    # when a library is imported, it takes active script as current directory and file is stored locally so have to
    # work out file path based on current directory
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(cur_dir, "ticks.json")

    # return file as pandas DataFrame
    return pd.read_json(file_path)


def generate_ticks(tick_increments: pd.DataFrame) -> np.ndarray:
    """
    Generate numpy list of ticks from list of {'Start', 'Stop', 'Step'} objects
    Output list is complete: [1.00, 1.01, ..., 1000]
    """
    return np.concatenate([
        np.arange(row.Start, row.Stop, row.Step)
        for index, row in tick_increments.iterrows()
    ])


def float_encode(v):
    """
    Encode a floating point number to integer format with x1000 scale
    """
    return round(v*1000)


def int_decode(v):
    """decode an integer encoded x1000 scale number to floating point actual value"""
    return v/1000


def closest_tick(value: float, return_index=False, round_down=False, round_up=False):
    """
    Convert an value to the nearest odds tick, e.g. 2.10000001 would be converted to 2.1
    Specify return_index=True to get index instead of value
    """
    return generic.closest_value(TICKS_DECODED, value, return_index=return_index, round_down=round_down,
                                 round_up=round_up)


# numpy array of Betfair ticks in integer encoded form
TICKS: np.ndarray = generate_ticks(get_tick_increments())

# list of Betfair ticks in integer encoded form
LTICKS = TICKS.tolist()

# numpy array of Betfair ticks in actual floating values
TICKS_DECODED: np.ndarray = int_decode(TICKS)

# list of Betfair ticks in actual floating values
LTICKS_DECODED = TICKS_DECODED.tolist()


def tick_spread(value_0: float, value_1: float, check_values: bool) -> int:
    """
    get tick spread between two odds values

    - if `check_values` is True and both values don't correspond to tick
    values, then 0 is returned
    - if `check_values` if False then the closest tick value is used for `value_0` and `value_1`

    Parameters
    ----------
    value_0 :
    value_1 :
    check_values:

    Returns
    -------

    """
    if check_values:

        # check that both values are valid odds
        if value_0 in LTICKS_DECODED and value_1 in LTICKS_DECODED:

            # get tick spread
            return abs(LTICKS_DECODED.index(value_0) - LTICKS_DECODED.index(value_1))

        else:

            # both values are not valid odds
            return 0

    else:

        # dont check values are valid odds, just use closet odds values
        return abs(closest_tick(value_0, return_index=True) - closest_tick(value_1, return_index=True))
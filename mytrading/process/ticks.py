import os
import numpy as np
import pandas as pd


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
    """Encode a floating point number to integer format with x1000 scale"""
    return round(v*1000)


def int_decode(v):
    """decode an integer encoded x1000 scale number to floating point actual value"""
    return v/1000


# numpy array of Betfair ticks in integer encoded form
TICKS: np.ndarray = generate_ticks(get_tick_increments())

# list of Betfair ticks in integer encoded form
LTICKS = TICKS.tolist()

# numpy array of Betfair ticks in actual floating values
TICKS_DECODED: np.ndarray = int_decode(TICKS)

# list of Betfair ticks in actual floating values
LTICKS_DECODED = TICKS_DECODED.tolist()



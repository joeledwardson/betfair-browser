from betfairlightweight.resources.bettingresources import MarketBook

from .windowprocessors import WindowProcessorTradedVolumeLadder, WindowProcessorLTPS
from .windowprocessors import WindowProcessorBestBack, WindowProcessorBestLay
from typing import List, Dict


def update_index_window(
        records: List,
        current_index, # index of current record - if streaming will just be the last record, needed for historical list
        seconds_window, # size of the window in seconds
        window_index, # index of window start to be updated and returned
        outside_window=True,
        f_pt=lambda r, i: r[i][0].publish_time):
    """
    increment 'window_index' until its timestamp is within 'seconds_window' seconds of the current record timestamp
    returns updated 'window_index' value.

    if 'outside_window' is specified as True, 'window_index' will be incremented until it precedes the record within
    the specified window - if False, 'window_index' will be incremented until it is the first record within the
    specified window
    """

    t = f_pt(records, current_index)
    while (window_index + outside_window) < current_index and \
            (t - f_pt(records, window_index + outside_window)).total_seconds() > seconds_window:
        window_index += 1
    return window_index


class Windows:
    """
    Hold a set of sliding windows, where the index of timestamped records outside sliding window is updated as current
    time increases.
    'windows' attribute holds dictionary of windows, indexed by their width in seconds

    Each window is a dict of:
    - 'window_index': index of record preceding the first in the window, i.e. if record index 5 was the first to be in
    the 60s window, then 'window_index' would be 4
    - 'window_prev_index': previous state of 'window_index', can be used to detect if 'window_index' has changed
    """

    # get indexed timestamp from record list
    @staticmethod
    def func_publish_time(record, index):
        return record[index].publish_time

    # Map window function names to classes
    FUNCTIONS = {
        'WindowProcessorTradedVolumeLadder': WindowProcessorTradedVolumeLadder,
        'WindowProcessorLTPS': WindowProcessorLTPS,
        'WindowProcessorBestBack': WindowProcessorBestBack,
        'WindowProcessorBestLay': WindowProcessorBestLay
    }

    def __init__(self):
        self.windows = {}

    # add a new window (if does not exist) by its width in seconds
    def add_window(self, width_seconds) -> Dict:
        if width_seconds not in self.windows:
            self.windows[width_seconds] = {
                'window_prev_index': 0,
                'window_index': 0,
                'function_configs': [],
                'function_instances': [],
            }
        return self.windows[width_seconds]

    # add a window processor to a window (assumes window exists)
    def add_function(self, width_seconds, function_key, **kwargs):
        window = self.windows[width_seconds]

        # check if any existing functions with the same args
        existing = [w for w in window['function_configs'] if w['name'] == function_key]
        if existing and any(e['kwargs'] == kwargs for e in existing):
            return

        window['function_configs'].append({
            'name': function_key,
            'kwargs': kwargs,
        })
        window['function_instances'].append(
            self.FUNCTIONS[function_key](window, **kwargs)
        )

    # update windows with a new received market book
    def update_windows(self, market_list: List[MarketBook], new_book: MarketBook):

        # loop windows
        for width_seconds, window in self.windows.items():

            # update previous state index of window start record
            window['window_prev_index'] = window['window_index']

            # update record index for window start
            window['window_index'] = update_index_window(
                records=market_list,
                current_index=len(market_list) - 1,
                seconds_window=width_seconds,
                window_index=window['window_index'],
                outside_window=True,
                f_pt=self.func_publish_time)

            # loop and run window processing functions
            for func in window['function_instances']:
                func.process_window(
                    market_list,
                    new_book,
                    window
                )


from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue
from mytrading.process.traded_volume import get_record_tv_diff
from mytrading.process.prices import best_price
from typing import List, Dict, Optional
from datetime import timedelta


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


class WindowProcessorBase:
    """
    Window processor
    Customise calculated values based on a window that can be used by multiple features
    Class has no information held inside, just a template for functions - all information should be stored in the
    window itself, only exception is constants defined in the class
    """

    def __init__(self, window: dict, **kwargs):
        pass

    def process_window(self, market_list: List[MarketBook], new_book: MarketBook, window: dict, **kwargs):
        raise NotImplementedError


class WindowProcessorTradedVolumeLadder(WindowProcessorBase):
    """
    Traded volume ladder window processor
    Stores a 'tv_diff_ladder' dict attribute in window, key is selection ID, value is ladder of 'price' and 'size'
    Stores a 'tv_diff_totals' dict attribute in window, key is selection ID, value is sum of 'price' elements in ladder
    """

    def __init__(self, window: dict, **kwargs):
        super().__init__(window, **kwargs)
        window['old_tv_ladders'] = {}

    def process_window(self, market_list: List[MarketBook], new_book: MarketBook, window: dict, **kwargs):

        # check if window start index has changed
        if window['window_index'] != window['window_prev_index']:

            # update window start tv ladders
            window['old_tv_ladders'] = {
                runner.selection_id: runner.ex.traded_volume
                for runner in market_list[window['window_index']].runners
            }

        # compute differences between current tv ladders and window starting tv ladders
        window['tv_diff_ladder'] = {
            runner.selection_id: get_record_tv_diff(
                runner.ex.traded_volume,
                window['old_tv_ladders'].get(runner.selection_id) or {},
                is_dict=True)
            for runner in new_book.runners
        }

        # sum tv differences
        window['tv_diff_totals'] = {
            selection_id: sum(x['size'] for x in ladder)
            for selection_id, ladder in window['tv_diff_ladder'].items()
        }


class WindowProcessorFeatureBase(WindowProcessorBase):
    """Store a list of runner attribute values within a runner window"""

    # key in window dictionary to store attribute values
    window_var: str = None

    # True only values inside window are stored, false to include value just before window starts
    inside_window = True

    def get_runner_attr(self, runner: RunnerBook):
        """define this method to get runner attribute (e.g. best back, last traded price etc.)"""
        raise NotImplementedError

    def __init__(self, window: dict, **kwargs):
        """initialise by creating empty dict in window using attribute key"""
        super().__init__(window, **kwargs)
        window[self.window_var] = {}

    def process_window(self, market_list: List[MarketBook], new_book: MarketBook, window: dict, **kwargs):

        # get starting index of window, add 1 if only taking values inside window
        start_index = window['window_index'] + self.inside_window

        # window dict -> in the attribute 'self.window_var' dict, each runner has lists of identical length with keys
        # as follows
        dict_elements = ['indexes', 'dts', 'values']

        for runner in new_book.runners:

            # if runner does not have a dictionary element then create one with empty lists
            if runner.selection_id not in window[self.window_var]:
                window[self.window_var][runner.selection_id] = {
                    k: [] for k in dict_elements
                }

            # get runner dictionary from window
            runner_dict = window[self.window_var][runner.selection_id]

            # remove from start of list values outside window valid record indexes
            while runner_dict['indexes']:
                if runner_dict['indexes'][0] >= start_index:
                    break
                for k in dict_elements:
                    runner_dict[k].pop(0)

            # get runner attribute value
            value = self.get_runner_attr(runner)

            # add current index, record datetime and value to runners list of elements
            if value:
                for k, v in {
                    'indexes': len(market_list) - 1,
                    'dts': new_book.publish_time,
                    'values': value
                }.items():
                    runner_dict[k].append(v)


class WindowProcessorLTPS(WindowProcessorFeatureBase):
    """store list of recent last traded prices"""

    window_var = 'runner_ltps'

    def get_runner_attr(self, runner: RunnerBook):
        return runner.last_price_traded


class WindowProcessorBestBack(WindowProcessorFeatureBase):
    """store list of recent best back prices"""

    windor_var = 'best_backs'

    def get_runner_attr(self, runner: RunnerBook):
        return best_price(runner.ex.available_to_back)


class WindowProcessorBestLay(WindowProcessorFeatureBase):
    """store list of recent best lay prices"""

    windor_var = 'best_lays'

    def get_runner_attr(self, runner: RunnerBook):
        return best_price(runner.ex.available_to_lay)


class WindowProcessorDelayerBase(WindowProcessorBase):
    """return a delayed window value"""

    # key to base value in window of which to be delayed
    base_key: str = None

    # key to list in window storing base values
    hist_key: str = None

    # key to value in dictionary storing delayed value
    delay_key: str = None

    def __init__(self, window: dict, delay_seconds: float, **kwargs):
        super().__init__(window, **kwargs)
        self.delay_seconds = delay_seconds
        window[self.delay_key] = {} # assuming index by runner ID
        window[self.hist_key] = []

    def process_window(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            window: dict,
            **kwargs
    ):
        # get new window value and add to historic list of not None
        new_value = window[self.base_key]
        if new_value:
            window[self.hist_key].push({'dt': new_book.publish_time, 'value': new_value})

        # remove all values, prior (getting second from bottom element) to element outside range
        while len(window[self.hist_key]) >= 2:
            if window[self.hist_key][1]['dt'] < (new_book.publish_time - timedelta(seconds=self.delay_seconds)):
                break

        # check list not empty before assigning
        if len(window[self.hist_key]):
            window[self.delay_key] = window[self.hist_key][0]


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


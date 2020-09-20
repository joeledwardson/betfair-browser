from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue
from myutils import betting
from typing import List, Dict, Optional


# increment 'window_index' until its timestamp is within 'seconds_window' seconds of the current record timestamp
# returns updated 'window_index' value.
# if 'outside_window' is specified as True, 'window_index' will be incremented until it precedes the record within
# the specified window - if False, 'window_index' will be incremented until it is the first record within the specified
# window
def update_index_window(
        records: List,
        current_index, # index of current record - if streaming this will just be the last record, needed for historical list
        seconds_window, # size of the window in seconds
        window_index, # index of window start to be updated and returned
        outside_window=True,
        f_pt=lambda r, i: r[i][0].publish_time):

    t = f_pt(records, current_index)
    while (window_index + outside_window) < current_index and \
            (t - f_pt(records, window_index + outside_window)).total_seconds() > seconds_window:
        window_index += 1
    return window_index


# Window processor
# Customise calculated values based on a window that can be used by multiple features
# Class has no information held inside, just a template for functions - all information should be stored in the
# window itself, only exception is constants defined in the class
class WindowProcessorBase:

    @classmethod
    def processor_init(cls, window: dict):
        pass

    @classmethod
    def process_window(cls, market_list: List[MarketBook], new_book: MarketBook, window: dict):
        raise NotImplementedError


# Traded volume ladder window processor
# Stores a 'tv_diff_ladder' dict attribute in window, key is selection ID, value is ladder of 'price' and 'size'
# Stores a 'tv_diff_totals' dict attribute in window, key is selection ID, value is sum of 'price' elements in ladder
class WindowProcessorTradedVolumeLadder(WindowProcessorBase):

    @classmethod
    def processor_init(cls, window: dict):
        window['old_tv_ladders'] = {}

    @classmethod
    def process_window(cls, market_list: List[MarketBook], new_book: MarketBook, window: dict):

        # check if window start index has changed
        if window['window_index'] != window['window_prev_index']:

            # update window start tv ladders
            window['old_tv_ladders'] = {
                runner.selection_id: runner.ex.traded_volume
                for runner in market_list[window['window_index']].runners
            }

        # compute differences between current tv ladders and window starting tv ladders
        window['tv_diff_ladder'] = {
            runner.selection_id: betting.get_record_tv_diff(
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


# store a list of runner values within a runner window
class WindowProcessorFeatureBase(WindowProcessorBase):

    window_var: str = None
    inside_window = True

    @classmethod
    def get_runner_attr(cls, runner: RunnerBook):
        raise NotImplementedError

    @classmethod
    def processor_init(cls, window: dict):
        window[cls.window_var] = {}

    @classmethod
    def process_window(cls, market_list: List[MarketBook], new_book: MarketBook, window: dict):

        start_index = window['window_index'] + cls.inside_window
        dict_elements = ['indexes', 'dts', 'values']

        for runner in new_book.runners:
            if runner.selection_id not in window[cls.window_var]:
                window[cls.window_var][runner.selection_id] = {
                    k: [] for k in dict_elements
                }

            runner_dict = window[cls.window_var][runner.selection_id]

            while runner_dict['indexes']:
                if runner_dict['indexes'][0] >= start_index:
                    break
                for k in dict_elements:
                    runner_dict[k].pop(0)

            value = cls.get_runner_attr(runner)
            if value:
                for k, v in {
                    'indexes': len(market_list) - 1,
                    'dts': new_book.publish_time,
                    'values': value
                }.items():
                    runner_dict[k].append(v)


# store list of recent last traded prices
class WindowProcessorLTPS(WindowProcessorFeatureBase):
    window_var = 'runner_ltps'

    @classmethod
    def get_runner_attr(cls, runner: RunnerBook):
        return runner.last_price_traded


# store list of recent best back prices
class WindowProcessorBestBack(WindowProcessorFeatureBase):
    windor_var = 'best_backs'

    @classmethod
    def get_runner_attr(cls, runner: RunnerBook):
        return betting.best_price(runner.ex.available_to_back)


# store list of recent best lay prices
class WindowProcessorBestLay(WindowProcessorFeatureBase):
    windor_var = 'best_lays'

    @classmethod
    def get_runner_attr(cls, runner: RunnerBook):
        return betting.best_price(runner.ex.available_to_lay)



# Hold a set of sliding windows, where the index of timestamped records outside sliding window is updated as current
# time increases.
# 'windows' attribute holds dictionary of windows, indexed by their width in seconds
# Each window is a dict of:
#   'window_index': index of record preceding the first in the window, i.e. if record index 5 was the first to be in
#   the 60s window, then 'window_index' would be 4
#   'window_prev_index': previous state of 'window_index', can be used to detect if 'window_index' has changed
class Windows:

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
                'functions': []
            }
        return self.windows[width_seconds]

    # add a window processor to a window (assumes window exists)
    def add_function(self, width_seconds, function_key):
        window = self.windows[width_seconds]
        if function_key not in window['functions']:
            window['functions'].append(function_key)
            self.FUNCTIONS[function_key].processor_init(window)

    # update windows with a new received market book
    def update_windows(self, market_list: List[MarketBook], new_book: MarketBook):

        # loop windows
        for width_seconds, w in self.windows.items():

            # update previous state index of window start record
            w['window_prev_index'] = w['window_index']

            # update record index for window start
            w['window_index'] = update_index_window(
                records=market_list,
                current_index=len(market_list) - 1,
                seconds_window=width_seconds,
                window_index=w['window_index'],
                outside_window=True,
                f_pt=self.func_publish_time)

            # loop and run window processing functions
            for func in w['functions']:
                self.FUNCTIONS[func].process_window(market_list, new_book, w)


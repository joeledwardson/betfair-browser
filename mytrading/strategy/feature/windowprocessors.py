from datetime import timedelta
from typing import List

from betfairlightweight.resources import MarketBook
from betfairlightweight.resources.bettingresources import RunnerBook

from myutils import mytiming
from myutils.myregistrar import MyRegistrar
from .featureprocessors import get_feature_processor
from mytrading.process.prices import best_price
from mytrading.process.tradedvolume import get_record_tv_diff


window_process_registrar = MyRegistrar()
window_registrar = MyRegistrar()


@window_process_registrar.register_element
def window_func_ltp(runner: RunnerBook):
    return runner.last_price_traded


@window_process_registrar.register_element
def window_func_best_back(runner: RunnerBook):
    return best_price(runner.ex.available_to_back)


@window_process_registrar.register_element
def window_func_best_lay(runner: RunnerBook):
    return best_price(runner.ex.available_to_lay)


class WindowProcessorBase:
    """
    Window processor
    Customise calculated values based on a window that can be used by multiple features
    Class has no information held inside, just a template for functions - all information should be stored in the
    window itself, only exception is constants defined in the class
    """

    def __init__(self, window: dict, window_s):
        self.window_s = window_s
        self.wp_identifier = self.__class__.__name__ + str(window_s)
        pass

    def process_window(self, market_list: List[MarketBook], new_book: MarketBook, window: dict):
        raise NotImplementedError


@window_registrar.register_element
class WindowProcessorTradedVolumeLadder(WindowProcessorBase):
    """
    Traded volume ladder window processor
    Stores a 'tv_diff_ladder' dict attribute in window, key is selection ID, value is ladder of 'price' and 'size'
    Stores a 'tv_diff_totals' dict attribute in window, key is selection ID, value is sum of 'price' elements in ladder
    """

    def __init__(self, window: dict, window_s):
        super().__init__(window, window_s)
        window['old_tv_ladders'] = {}

    @mytiming.timing_register_attr(name_attr='wp_identifier')
    def process_window(self, market_list: List[MarketBook], new_book: MarketBook, window: dict):

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


@window_registrar.register_element
class WindowProcessorFeatureBase(WindowProcessorBase):
    """Store a list of runner attribute values within a runner window"""
    def get_runner_attr(self, runner: RunnerBook, window):
        """this method gets runner attribute using stored function"""
        value = self.window_func(runner)
        if value is not None:
            return self.processor_func(
                value,
                window[self.window_var][runner.selection_id]['values'],
                window[self.window_var][runner.selection_id]['dts']
            )
        else:
            return None

    def __init__(
            self,
            window: dict,
            window_s,
            window_var: str,
            window_func_key: str,
            inside_window=True,
            feature_processor_key=None,
            feature_processor_kwargs=None,
    ):
        """initialise by creating empty dict in window using attribute key"""
        super().__init__(window, window_s)
        self.wp_identifier = self.wp_identifier + '.' + window_func_key

        # key in window dictionary to store attribute values
        self.window_var: str = window_var

        # function to retrieve runner data
        self.window_func = window_process_registrar[window_func_key]

        # True only values inside window are stored, false to include value just before window starts
        self.inside_window = inside_window

        self.processor_func = get_feature_processor(
            feature_processor_key or 'value_processor_identity',
            feature_processor_kwargs
        )

        window[self.window_var] = {}

    @mytiming.timing_register_attr(name_attr='wp_identifier')
    def process_window(self, market_list: List[MarketBook], new_book: MarketBook, window: dict):

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
            value = self.get_runner_attr(runner, window)

            # add current index, record datetime and value to runners list of elements
            if value:
                for k, v in {
                    'indexes': len(market_list) - 1,
                    'dts': new_book.publish_time,
                    'values': value
                }.items():
                    runner_dict[k].append(v)

#
# class WindowProcessorLTPS(WindowProcessorFeatureBase):
#     """store list of recent last traded prices"""
#
#     window_var = 'runner_ltps'
#
#     def get_runner_attr(self, runner: RunnerBook):
#         return runner.last_price_traded
#
#
# class WindowProcessorBestBack(WindowProcessorFeatureBase):
#     """store list of recent best back prices"""
#
#     windor_var = 'best_backs'
#
#     def get_runner_attr(self, runner: RunnerBook):
#         return best_price(runner.ex.available_to_back)
#
#
# class WindowProcessorBestLay(WindowProcessorFeatureBase):
#     """store list of recent best lay prices"""
#
#     windor_var = 'best_lays'
#
#     def get_runner_attr(self, runner: RunnerBook):
#         return best_price(runner.ex.available_to_lay)


# TODO - depreciated?
# class WindowProcessorDelayerBase(WindowProcessorBase):
#     """return a delayed window value"""
#
#     # key to base value in window of which to be delayed
#     base_key: str = None
#
#     # key to list in window storing base values
#     hist_key: str = None
#
#     # key to value in dictionary storing delayed value
#     delay_key: str = None
#
#     def __init__(self, window: dict, window_s, delay_seconds: float):
#         super().__init__(window, window_s)
#         self.delay_seconds = delay_seconds
#         window[self.delay_key] = {} # assuming index by runner ID
#         window[self.hist_key] = []
#
#     def process_window(
#             self,
#             market_list: List[MarketBook],
#             new_book: MarketBook,
#             window: dict,
#             **kwargs
#     ):
#         # get new window value and add to historic list of not None
#         new_value = window[self.base_key]
#         if new_value:
#             window[self.hist_key].push({'dt': new_book.publish_time, 'value': new_value})
#
#         # remove all values, prior (getting second from bottom element) to element outside range
#         while len(window[self.hist_key]) >= 2:
#             if window[self.hist_key][1]['dt'] < (new_book.publish_time - timedelta(seconds=self.delay_seconds)):
#                 break
#
#         # check list not empty before assigning
#         if len(window[self.hist_key]):
#             window[self.delay_key] = window[self.hist_key][0]
#

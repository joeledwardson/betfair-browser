from __future__ import annotations
from betfairlightweight.resources.bettingresources import MarketBook
import numpy as np
from typing import List, Dict, Optional
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import logging
from os import path
from collections import deque
import pandas as pd
import statistics

from .featureprocessors import get_feature_processor, get_feature_processors
from mytrading.process.prices import best_price
from mytrading.process.tradedvolume import traded_runner_vol
from mytrading.process.ticks.ticks import tick_spread, LTICKS_DECODED
from mytrading.process.tradedvolume import get_record_tv_diff
from mytrading.utils.storage import construct_hist_dir
from mytrading.oddschecker import oc_hist_mktbk_processor
from .window import Windows
from myutils import mytiming, myregistrar


ftrs_reg = myregistrar.MyRegistrar()
active_logger = logging.getLogger(__name__)


class BetfairFeatureException(Exception):
    pass


# TODO - add function indicate if value changed, write values incrementally to file
# TODO - how to store values without list getting too big? maybe accept arg which dicates how large to set the
#  "cache" size, i.e. how many values to store in list - or a overridable function which removes values from deque
#  that arent needed
# TODO - output cache?
class RFBase:
    """
    base class for runner features

    - value_processor: process output values by selecting processor from `runner_feature_value_processors` - processed
    values will be taken from `.values` into `.processed_values`
    - value_processor_args: kwargs to pass to `value_processor` function creator
    - periodic_ms: specify to only compute and store feature value every 'periodic_ms' milliseconds
    - period_timestamps: only valid is `periodic_ms` is not None, specifies if timestamps should be sampled
    - components: list of dictionary specifications for sub-features, i.e. features that base some of their
    calculations on the existing feature, dictionary values are:
        key: human name of feature for dictionary 'self.sub_features', (.e.g 'my minimum')
        values:
            'name': feature name as matches file (e.g.  'RunnerFeatureTradedWindowMin')
            'kwargs': arguments to pass to sub feature constructor
    """
    def __init__(
            self,
            sub_features_config: Optional[Dict] = None,
            parent: Optional[RFBase] = None,
            feature_key=None,  # TODO - rename to 'name'
            cache_count=2,
            cache_secs=None,
            cache_insidewindow=None,
    ):

        self.parent = parent
        self.selection_id: int = None
        if feature_key:
            self.ftr_identifier = feature_key
        else:
            self.ftr_identifier = self.__class__.__name__
        if self.parent:
            self.ftr_identifier = '.'.join([
                self.parent.ftr_identifier,
                self.ftr_identifier
            ])

        self.values_cache = deque()
        self.out_cache = deque()
        self.cache_count = cache_count
        self.cache_secs = cache_secs
        self.inside_window = cache_insidewindow

        self.sub_features: Dict[str, RFBase] = {}
        if sub_features_config:
            if type(sub_features_config) is not dict:
                raise BetfairFeatureException(
                    f'error in feature "{self.ftr_identifier}", sub features config is not dict'
                )
            for k, v in sub_features_config.items():
                if type(v) is not dict:
                    raise BetfairFeatureException(
                        f'error in feature "{self.ftr_identifier}", sub-feature "{k}" value is not dict'
                    )
                if 'name' not in v:
                    raise BetfairFeatureException(
                        f'error in feature "{self.ftr_identifier}", sub-feature "{k}", no name element in dict'
                    )
                feature_class = ftrs_reg[v['name']]
                feature_kwargs = v.get('kwargs', {})
                try:
                    self.sub_features[k] = feature_class(
                        parent=self,
                        **feature_kwargs,
                        feature_key=k, # use dictionary name as feature name
                    )
                except TypeError as e:
                    raise BetfairFeatureException(
                        f'error in feature "{self.ftr_identifier}", sub-feature "{k}": {e}'
                    )

    def is_new_value(self) -> bool:
        return len(self.values_cache) == 1 or \
               (len(self.values_cache) >= 2 and self.values_cache[-1][2] != self.values_cache[-2][2])

    def update_cache(self):
        if self.cache_secs:
            if len(self.values_cache):
                dt = self.values_cache[-1][0]
                dtw = dt - timedelta(seconds=self.cache_secs)
                idx = 0 if self.inside_window else 1
                while len(self.values_cache) > idx:
                    if self.values_cache[idx][0] >= dtw:
                        break
                    else:
                        self.values_cache.popleft()
        else:
            while len(self.values_cache) > self.cache_count:
                self.values_cache.popleft()

    def race_initializer(self, selection_id: int, first_book: MarketBook):
        """initialize feature with first market book of race and selected runner"""
        self.selection_id = selection_id
        for sub_feature in self.sub_features.values():
            sub_feature.race_initializer(selection_id, first_book)

    def publish_update(self, new_book, runner_index, pt=None):
        # get feature value, ignore if None
        value = self.runner_update(new_book, runner_index)
        if value is None:
            return

        # if publish time not explicitly passed, use parent if exist else market book
        if pt is None:
            if self.parent is None:
                pt = new_book.publish_time
            else:
                pt = self.parent.values_cache[-1][0]

        self.values_cache.append((pt, value))
        self.out_cache.append((pt, value))
        self.update_cache()

        for sub_feature in self.sub_features.values():
            sub_feature.process_runner(new_book, runner_index)

    @mytiming.timing_register_attr(name_attr='ftr_identifier')
    def process_runner(self, new_book: MarketBook, runner_index):
        """update feature value and add to cache"""
        self.publish_update(new_book, runner_index)

    def runner_update(self, new_book: MarketBook, runner_index):
        """
        implement this function to return feature value from new market book received
        return None if do not want value to be stored
        """
        raise NotImplementedError

    # @classmethod
    # def pre_serialize(cls, plotly_data: List[Dict]) -> List[Dict]:
    #     """
    #     pre-process for serialization of data
    #     """
    #     data = plotly_data.copy()
    #     for entry in data:
    #         entry['x'] = [x.timestamp() for x in entry['x']]
    #     return data
    #
    # @classmethod
    # def post_de_serialize(cls, plotly_data: List[Dict]) -> None:
    #     """
    #     post_process de-serialized feature plotly data
    #     """
    #     for entry in plotly_data:
    #         entry['x'] = [datetime.fromtimestamp(x) for x in entry['x']]
    #
    # # TODO - remove this, should not be storing complete list of values, instead from file
    # def get_plotly_data(self):
    #     """
    #     get feature data in list of plotly form dicts, where 'x' is timestamps and 'y' are feature values
    #     by default only one entry is returned, but this style leaves the possibility open for returning list of dicts
    #     for inheritance base method overloading, must adhere to rules:
    #     - be list of dicts
    #     - each dict entry be a list of values
    #     - 'x' key values must be datetime entries for feature so can serialize
    #     """
    #     return [{
    #         'x': self.dts,
    #         'y': self.processed_vals
    #     }]

    def last_value(self):
        """get most recent value processed, if empty return None"""
        return self.values_cache[-1][1] if len(self.values_cache) else None


@ftrs_reg.register_element
class RFChild(RFBase):
    """
    feature that must be used as a sub-feature to existing feature
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if kwargs.get('parent') is None:
            raise BetfairFeatureException(f'sub-feature has not received "parent" argument')

    def runner_update(self, new_book: MarketBook, runner_index):
        return self.parent.last_value()


@ftrs_reg.register_element
class RFMvAvg(RFChild):
    """moving average of parent values"""
    def runner_update(self, new_book: MarketBook, runner_index):
        if len(self.parent.values_cache):
            return statistics.mean([v[1] for v in self.parent.values_cache])


@ftrs_reg.register_element
class RFSample(RFChild):
    """sample values to periodic timestamps with most recent value"""
    def __init__(self, periodic_ms, **kwargs):
        super().__init__(**kwargs)
        self.periodic_ms = periodic_ms
        self.last_timestamp: datetime = None

    def race_initializer(self, selection_id: int, first_book: MarketBook):
        super().race_initializer(selection_id, first_book)
        self.last_timestamp = first_book.publish_time.replace(microsecond=0)

    def process_runner(self, new_book: MarketBook, runner_index):
        # if data is sampled and more than one sample time has elapsed, fill forwards until time is met
        while int((new_book.publish_time - self.last_timestamp).total_seconds() * 1000) > self.periodic_ms:
            self.last_timestamp = self.last_timestamp + timedelta(milliseconds=self.periodic_ms)
            self.publish_update(new_book, runner_index, self.last_timestamp)


@ftrs_reg.register_element
class RFTVLad(RFBase):
    def runner_update(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].ex.traded_volume or None


@ftrs_reg.register_element
class RFTVLadDif(RFChild):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if type(self.parent) is not RFTVLad:
            raise BetfairFeatureException('expected traded vol feature parent')

    def runner_update(self, new_book: MarketBook, runner_index):
        if len(self.parent.values_cache) >= 2:
            return get_record_tv_diff(
                self.parent.values_cache[-1][1],
                self.parent.values_cache[0][1]
            )
        else:
            return None


class _RFTVLadDifFunc(RFChild):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if type(self.parent) is not RFTVLadDif:
            raise BetfairFeatureException('expected traded vol diff feature parent')

    def runner_update(self, new_book: MarketBook, runner_index):
        if len(self.parent.values_cache):
            tvs = self.parent.values_cache[-1][1]
            if len(tvs):
                return self.lad_func(tvs)
        return None

    def lad_func(self, tvs):
        raise NotImplementedError


@ftrs_reg.register_element
class RFTVLadMax(_RFTVLadDifFunc):
    def lad_func(self, tvs):
        v = max([x['price'] for x in tvs])
        return v


@ftrs_reg.register_element
class RFTVLadMin(_RFTVLadDifFunc):
    def lad_func(self, tvs):
        v = min([x['price'] for x in tvs])
        return v


@ftrs_reg.register_element
class RFTVLadTot(_RFTVLadDifFunc):
    def lad_func(self, tvs):
        v = sum([x['size'] for x in tvs])
        return v


@ftrs_reg.register_element
class RFBkSplit(RFBase):
    """
    traded volume since previous update that is above current best back price
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_best_back = None
        self.previous_best_lay = None
        self.previous_ladder = dict()

    def runner_update(self, new_book: MarketBook, runner_index):

        runner = new_book.runners[runner_index]
        value = None

        if self.previous_best_back and self.previous_best_lay:
            diff = get_record_tv_diff(
                runner.ex.traded_volume,
                self.previous_ladder
            )
            # difference in new back and lay money
            back_diff = sum([x['size'] for x in diff if x['price'] <= self.previous_best_back])
            lay_diff = sum([x['size'] for x in diff if x['price'] >= self.previous_best_lay])
            value = back_diff - lay_diff

        # update previous state values
        self.previous_best_back = best_price(runner.ex.available_to_back)
        self.previous_best_lay = best_price(runner.ex.available_to_lay)
        self.previous_ladder = runner.ex.traded_volume

        return value


@ftrs_reg.register_element
class RFLTP(RFBase):
    """Last traded price of runner"""
    def runner_update(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].last_price_traded


@ftrs_reg.register_element
class RFWOM(RFBase):
    """
    Weight of money (difference of available-to-lay to available-to-back)
    applied to `wom_ticks` number of ticks on BACK and LAY sides of the book
    """
    def __init__(self, wom_ticks, **kwargs):
        super().__init__(**kwargs)
        self.wom_ticks = wom_ticks

    def runner_update(self, new_book: MarketBook, runner_index):
        atl = new_book.runners[runner_index].ex.available_to_lay
        atb = new_book.runners[runner_index].ex.available_to_back

        if atl and atb:
            back = sum([x['size'] for x in atb[:self.wom_ticks]])
            lay = sum([x['size'] for x in atl[:self.wom_ticks]])
            return lay - back
        else:
            return None


@ftrs_reg.register_element
class RFBck(RFBase):
    """Best available back price of runner"""
    def runner_update(self, new_book: MarketBook, runner_index):
        return best_price(new_book.runners[runner_index].ex.available_to_back)


@ftrs_reg.register_element
class RFLay(RFBase):
    """
    Best available lay price of runner
    """
    def runner_update(self, new_book: MarketBook, runner_index):
        return best_price(new_book.runners[runner_index].ex.available_to_lay)


@ftrs_reg.register_element
class RFLadSprd(RFBase):
    """
    tick spread between best lay and best back - defaults to 1000 if cannot find best back or lay
    """
    def runner_update(self, new_book: MarketBook, runner_index):
        best_lay = best_price(new_book.runners[runner_index].ex.available_to_lay)
        best_back = best_price(new_book.runners[runner_index].ex.available_to_back)
        if best_lay and best_back:
            return tick_spread(best_back, best_lay, check_values=False)
        else:
            return len(LTICKS_DECODED)


@ftrs_reg.register_element
class RFLadBck(RFBase):
    """
    best available price-sizes on back side within specified number of elements of best price
    """
    def __init__(self, n_elements, *args, **kwargs):
        self.n_elements = n_elements
        super().__init__(*args, **kwargs)

    def runner_update(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].ex.available_to_back[:self.n_elements]


@ftrs_reg.register_element
class RFLadLay(RFBase):
    """
    best available price-sizes on lay side within specified number of elements of best price
    """
    def __init__(self, n_elements, *args, **kwargs):
        self.n_elements = n_elements
        super().__init__(*args, **kwargs)

    def runner_update(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].ex.available_to_lay[:self.n_elements]


@ftrs_reg.register_element
class RFMax(RFChild):
    """
    perform a feature processor function on windowed parent values
    """
    def runner_update(self, new_book: MarketBook, runner_index):
        if len(self.parent.values_cache) >= 1:
            return max(abs(np.diff([v[1] for v in self.parent.values_cache])).tolist())
        else:
            return 0


@ftrs_reg.register_element
class RFTVTot(RFBase):
    """
    total traded volume of runner
    """
    def runner_update(self, new_book: MarketBook, runner_index):
        return traded_runner_vol(new_book.runners[runner_index])

#
# @ftrs_reg.register_element
# class RunnerFeatureSubRegression(RFChild):
#
#     """
#     Perform regressions on a runner values as a sub-feature
#     - regression_preprocessor: apply pre-processor to feature values before performing linear regression (select from
#     RunnerFeatureValueProcessors)
#     """
#
#     def __init__(
#             self,
#             element_count,
#             regression_preprocessor: str = 'value_processor_identity',
#             regression_preprocessor_args: dict = None,
#             *args,
#             **kwargs):
#         """
#
#         Parameters
#         ----------
#         element_count : number of elements at which to perform regression across
#         regression_preprocessor : name of preprocessor function to use
#         regression_preprocessor_args : kwargs passed to preprocessor function constructor
#         args :
#         kwargs :
#         """
#         super().__init__(
#             *args,
#             **kwargs,
#         )
#         self.element_count = element_count
#         self.regression_preprocessor = get_feature_processor(regression_preprocessor, regression_preprocessor_args)
#
#     def runner_update(self, new_book: MarketBook, runner_index):
#
#         dts = self.parent.dts[-self.element_count:]
#         x = [(x - new_book.publish_time).total_seconds() for x in dts]
#         y = self.parent.processed_vals[-self.element_count:]
#
#         if not x or not y or len(x) != len(y):
#             return None
#
#         if len(x) < self.element_count:
#             return None
#
#         y_processed = [self.regression_preprocessor(v, y, dts) for v in y]
#         X = np.expand_dims(x, -1)
#         reg = LinearRegression().fit(X, y_processed)
#
#         if len(reg.coef_) == 1:
#
#             return {
#                     'gradient': reg.coef_[0],
#                     'rsquared': reg.score(X, y_processed)
#                 }
#
#         return None
#
#     def computation_buffer_seconds(self) -> int:
#         if not self.parent.periodic_ms:
#             active_logger.warning(f'regression sub feature expected parent to have periodic ms')
#             return 0
#         else:
#             return int((self.parent.periodic_ms * self.element_count) / 1000)
#

# @ftrs_reg.register_element
# class RunnerFeatureHistoricOddscheckerAvg(RFBase):
#     """
#     get oddschecker average value between bookies (not exchanges) for runner
#     oddschecker file and catalogue file is retrieved using recorded directory as historic base, passed on feature
#     constructor
#     """
#     def __init__(
#             self,
#             recorded_dir: str,
#             *args,
#             **kwargs
#     ):
#         super().__init__(*args, **kwargs)
#         self.recorded_dir = recorded_dir
#         self.oc_dict = dict()
#         self.oc_avg = None
#
#     def race_initializer(self, selection_id: int, first_book: MarketBook):
#         super().race_initializer(selection_id, first_book)
#
#         market_dir = path.join(self.recorded_dir, construct_hist_dir(first_book))
#         self.oc_dict = oc_hist_mktbk_processor(first_book.market_id, market_dir, name_attr='runner_name')
#         if self.oc_dict['ok']:
#             if self.selection_id in self.oc_dict['oc_sorted']:
#                 self.oc_avg = self.oc_dict['oc_sorted'][self.selection_id]
#
#     def runner_update(self, new_book: MarketBook, runner_index):
#         return self.oc_avg



#
# @ftrs_reg.register_element
# class RunnerFeatureBiggestDifference(RunnerFeatureWindowBase):
#     """
#     get biggest difference between sequential window values
#     parent feature must have created a window processor of type `WindowProcessorFeatureBase` so that window data has
#     'values' key
#     """
#     def __init__(self, window_var, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.window_key = window_var
#         # if not isinstance(self.parent, RunnerFeatureWindowBase):
#         #     raise Exception(f'sub feature {self.__name__} expected parent to be of type RunnerFeatureWindowBase')
#
#     def runner_update(self, new_book: MarketBook, runner_index):
#         values = self.window[self.window_key][self.selection_id]['values']
#         if len(values) >= 2:
#             return max(abs(np.diff(values)).tolist())
#         return None


# class RFDly(RFChild):
#     """
#     track a delay by x number of seconds
#     """
#     def __init__(self, delay_seconds, outside_window=True, *args, **kwargs):
#         self.delay_seconds = delay_seconds
#         self.delay_index = 0
#         self.outside_window = outside_window
#         self._td = timedelta(seconds=delay_seconds)
#         super().__init__(*args, **kwargs)
#
#     @mytiming.timing_register
#     def update_delay_index(self, pt):
#         n = len(self.parent.processed_vals)
#         dt = pt - self._td
#         while (self.delay_index + 1) < n and \
#                 self.parent.dts[self.delay_index + self.outside_window] < dt:
#             self.delay_index += 1

#
# @ftrs_reg.register_element
# class RunnerFeatureSubDelayComparison(_RunnerFeatureSubDelayer):
#     """
#     compare a parent feature current value to delayed value
#     """
#     def runner_update(self, new_book: MarketBook, runner_index):
#         self.update_delay_index(new_book.publish_time)
#         if len(self.parent.processed_vals):
#             previous_value = self.parent.processed_vals[self.delay_index]
#             current_value = self.parent.last_value()
#             if previous_value is not None and current_value is not None:
#                 return current_value - previous_value


# @ftrs_reg.register_element
# class RunnerFeatureSubSum(_RunnerFeatureSubDelayer):
#     """
#     sum a parent feature values over x number of seconds
#     """
#     def runner_update(self, new_book: MarketBook, runner_index):
#         self.update_delay_index(new_book.publish_time)
#         n = len(self.parent.processed_vals)
#         assert n >= self.delay_index
#         if n:
#             return sum(self.parent.processed_vals[self.delay_index:])


# @ftrs_reg.register_element
# class RunnerFeatureSubConstDelayer(RFChild):
#     """
#     get last parent feature value that has held its value without changing for x number of seconds
#     """
#
#     def __init__(self, hold_seconds, *args, **kwargs):
#         self.hold_seconds = hold_seconds
#         self.value_timestamp: datetime = datetime.now()
#         self.parent_previous = None
#         self.hold_value = None
#         super().__init__(*args, **kwargs)
#
#     def race_initializer(self, selection_id: int, first_book: MarketBook):
#         self.value_timestamp = first_book.publish_time
#
#     def runner_update(self, new_book: MarketBook, runner_index):
#
#         parent_current = self.parent.last_value()
#         if self.parent_previous is None:
#             self.parent_previous = parent_current
#
#         if self.parent_previous is not None and parent_current is not None:
#             if self.parent_previous != parent_current:
#                 self.value_timestamp = new_book.publish_time
#
#             if (new_book.publish_time - self.value_timestamp).total_seconds() >= self.hold_seconds:
#                 self.hold_value = parent_current
#
#         self.parent_previous = parent_current
#         return self.hold_value

#
# @ftrs_reg.register_element
# class RunnerFeatureSubLastValue(RFChild):
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#         # store parent active value (until change)
#         self.active_value = None
#
#     def runner_update(self, new_book: MarketBook, runner_index):
#
#         # check parent value list not empty
#         if len(self.parent.processed_vals):
#
#             # get most recent value from parent
#             current_value = self.parent.processed_vals[-1]
#
#             # check if active value is None
#             if self.active_value is None:
#
#                 # first initialisation, just use value dont check for change
#                 self.active_value = current_value
#                 return current_value
#
#             # check if current parent value is different from stored active value
#             elif current_value != self.active_value:
#
#                 # stored active value is now previous value
#                 previous_value = self.active_value
#
#                 # update active value
#                 self.active_value = current_value
#
#                 # return previous state value
#                 return previous_value


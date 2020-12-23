from __future__ import annotations
from betfairlightweight.resources.bettingresources import MarketBook
import numpy as np
from typing import List, Dict
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
import operator
import statistics
from datetime import datetime, timedelta
import logging
from ..process.prices import best_price
from ..process.tradedvolume import traded_runner_vol
from ..process.ticks.ticks import tick_spread, LTICKS_DECODED
from .window import Windows


features_dict = {}
active_logger = logging.getLogger(__name__)


def register_feature(cls):
    """
    register a feature, add to dictionary of features
    """
    if cls.__name__ in features_dict:
        raise Exception(f'registering feature "{cls.__name__}", but already exists!')
    else:
        features_dict[cls.__name__] = cls
        return cls


class BetfairFeatureException(Exception):
    pass


class RunnerFeatureValueProcessors:
    """
    List of value processors which can apply simple processing functions to feature output values (e.g. scaling,
    mean over n periods etc)

    Value processors (named value_processor_xxx) take arguments to customise the returned function to be used as the
    value processor
    Value processors must adhere to the format:
        function(value, values, datetimes)

    To use a value processor, pass the function name as a string to `value_processor` when creating a feature
    instance, with any kwargs specified in `value_processor_args`
    """
    @staticmethod
    def value_processor_identity():
        """
        return same value
        """
        def inner(value, values: List, datetimes: List[datetime]):
            return value
        return inner

    @staticmethod
    def value_processor_moving_average(n_entries):
        """
        moving average over `n_entries`
        """
        def inner(value, values: List, datetimes: List[datetime]):
            return statistics.mean(values[-n_entries:])
        return inner

    @staticmethod
    def value_processor_invert():
        """
        get 1/value unless value is 0 where return 0
        """
        def inner(value, values: List, datetimes: List[datetime]):
            return 1 / value if value != 0 else 0
        return inner

    @classmethod
    def get_processor(cls, name):
        """retrieve processor by function name"""
        if name not in cls.__dict__:
            raise BetfairFeatureException(f'"{name}" not found in processors')
        else:
            return getattr(cls, name)


class RunnerFeatureBase:
    """
    base class for runner features

    - value_processor: process output values by selecting processor from `RunnerFeatureValueProcessors` - processed
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
            value_processor: str = 'value_processor_identity',
            value_processor_args: dict = None,
            periodic_ms: int = None,
            periodic_timestamps: bool = False,
            sub_features_config: Dict = None,
            parent: RunnerFeatureBase = None,
    ):

        self.parent: RunnerFeatureBase = parent
        self.windows: Windows = None
        self.selection_id: int = None

        self.values = []
        self.dts = []

        def _get_processor(name, _kwargs):
            creator = RunnerFeatureValueProcessors.get_processor(name)
            return creator(**(_kwargs if _kwargs else {}))

        self.value_processor = _get_processor(value_processor, value_processor_args)
        self.processed_vals = []

        self.sub_features: Dict[str, RunnerFeatureBase] = {}
        if sub_features_config:
            for k, v in sub_features_config.items():
                feature_class = globals()[v['name']]
                feature_kwargs = v.get('kwargs', {})
                self.sub_features[k] = feature_class(
                    parent=self,
                    **feature_kwargs
                )

        self.periodic_ms = periodic_ms
        self.periodic_timestamps = periodic_timestamps
        self.last_timestamp: datetime = None

    def race_initializer(
            self,
            selection_id: int,
            first_book: MarketBook,
            windows: Windows):
        """initialize feature with first market book of race and selected runner"""

        self.last_timestamp = first_book.publish_time
        self.selection_id = selection_id
        self.windows = windows

        for sub_feature in self.sub_features.values():
            sub_feature.race_initializer(selection_id, first_book, windows)

    def process_runner(
            self, market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):
        """
        calls `self.runner_update()` to obtain feature value and if not None appends to list of values with timestamp
        """

        publish_time = new_book.publish_time
        update = False

        # if specified, updates only allow every 'periodic_ms' milliseconds
        if self.periodic_ms:

            # check if current book is 'periodic_ms' milliseconds past last update
            if int((new_book.publish_time - self.last_timestamp).total_seconds() * 1000) > self.periodic_ms:

                # specify that do want to update
                update = True

                # increment previous timestamps
                self.last_timestamp = self.last_timestamp + timedelta(milliseconds=self.periodic_ms)

                # if periodically timestamped flag specified, set timestamp to sampled time
                if self.periodic_timestamps:
                    publish_time = self.last_timestamp

        # if periodic update milliseconds not specified, update regardless
        else:
            update = True

        # if criteria for updating value not met the ignore
        if not update:
            return

        # add datetime, value and processed value to lists
        def send_update(_publish_time):

            # get feature value, ignore if None
            value = self.runner_update(market_list, new_book, windows, runner_index)
            if value is None:
                return

            # if sub-feature, use parent timestamp
            if self.parent is not None and self.parent.dts:
                _publish_time = self.parent.dts[-1]

            # add raw value and timestamp to lists
            self.dts.append(_publish_time)
            self.values.append(value)

            # compute value processor on raw value
            processed = self.value_processor(value, self.values, self.dts)

            # add processed value
            self.processed_vals.append(processed)

            for sub_feature in self.sub_features.values():
                sub_feature.process_runner(market_list, new_book, windows, runner_index)

        send_update(publish_time)

        # if data is sampled and more than one sample time has elapsed, fill forwards until time is met
        if self.periodic_ms:
            while int((new_book.publish_time - self.last_timestamp).total_seconds() * 1000) > self.periodic_ms:
                self.last_timestamp = self.last_timestamp + timedelta(milliseconds=self.periodic_ms)
                if self.periodic_timestamps:
                    send_update(self.last_timestamp)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):
        """
        implement this function to return feature value from new market book received
        return None if do not want value to be stored
        """
        raise NotImplementedError

    @classmethod
    def pre_serialize(cls, plotly_data: List[Dict]) -> List[Dict]:
        """
        pre-process for serialization of data
        """
        data = plotly_data.copy()
        for entry in data:
            entry['x'] = [x.timestamp() for x in entry['x']]
        return data

    @classmethod
    def post_de_serialize(cls, plotly_data: List[Dict]) -> None:
        """
        post_process de-serialized feature plotly data
        """
        for entry in plotly_data:
            entry['x'] = [datetime.fromtimestamp(x) for x in entry['x']]

    def get_plotly_data(self):
        """
        get feature data in list of plotly form dicts, where 'x' is timestamps and 'y' are feature values
        by default only one entry is returned, but this style leaves the possibility open for returning list of dicts
        for inheritance base method overloading, must adhere to rules:
        - be list of dicts
        - each dict entry be a list of values
        - 'x' key values must be datetime entries for feature so can serialize
        """
        return [{
            'x': self.dts,
            'y': self.processed_vals
        }]

    def last_value(self):
        """get most recent value processed, if empty return None"""
        return self.processed_vals[-1] if len(self.processed_vals) else None

    def computation_buffer_seconds(self) -> int:
        """
        get the number of additional seconds prior to start of analysis needed for computation.
        e.g. if function compares traded vol to 60 seconds go, return 60 to indicate that need to compute feature 60s
        before start of analysis

        Returns
        -------

        """
        return 0


@register_feature
class RunnerFeatureWindowBase(RunnerFeatureBase):
    """
    base feature utilizing a window function (see bf_Windows)

    - where `window_s` is the width in seconds of the window in which to trace values
    - `window_function` is the name of the window processing function, applied when the window updates
    """

    def __init__(
            self,
            window_s,
            window_function: str,
            **kwargs
    ):
        super().__init__(**kwargs)

        self.window: dict = None
        self.window_s = window_s
        self.window_function = window_function

    def race_initializer(
            self,
            selection_id: int,
            first_book: MarketBook,
            windows: Windows):
        """
        add window of specified number of seconds to Windows instance and add specified window function when first
        market book received
        """

        super().race_initializer(selection_id, first_book, windows)
        self.window = windows.add_window(self.window_s)
        windows.add_function(self.window_s, self.window_function)

    def computation_buffer_seconds(self) -> int:
        return self.window_s


@register_feature
class RunnerFeatureTradedWindowMin(RunnerFeatureWindowBase):
    """Minimum of recent traded prices in last 'window_s' seconds"""

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorLTPS', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        values = self.window['runner_ltps'][self.selection_id]['values']

        if len(values):
            return min(values)
        else:
            return None


@register_feature
class RunnerFeatureTradedWindowMax(RunnerFeatureWindowBase):
    """Maximum of recent traded prices in last 'window_s' seconds"""

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorLTPS', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        values = self.window['runner_ltps'][self.selection_id]['values']

        if len(values):
            return max(values)
        else:
            return None


@register_feature
class RunnerFeatureBookSplitWindow(RunnerFeatureWindowBase):
    """
     percentage of recent traded volume in the last 'window_s' seconds that is above current best back price
    """

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorTradedVolumeLadder', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        # best back price on current record
        best_back = best_price(new_book.runners[runner_index].ex.available_to_back)

        if best_back:

            # difference in traded volume ladder and totals for recent records
            ladder_diffs = self.window['tv_diff_ladder'][self.selection_id]
            total_diff = self.window['tv_diff_totals'][self.selection_id]

            # sum of money for recent traded volume trying to back
            back_diff = sum([x['size'] for x in ladder_diffs if x['price'] > best_back])

            # percentage of volume trying to back compared to total (back & lay)
            if total_diff:
                return back_diff / total_diff

        return None


@register_feature
class RunnerFeatureLTP(RunnerFeatureBase):
    """Last traded price of runner"""
    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):
        return new_book.runners[runner_index].last_price_traded


@register_feature
class RunnerFeatureWOM(RunnerFeatureBase):
    """
    Weight of money (difference of available-to-lay to available-to-back)

    applied to `wom_ticks` number of ticks on BACK and LAY sides of the book
    """

    def __init__(self, wom_ticks, **kwargs):
        super().__init__(**kwargs)
        self.wom_ticks = wom_ticks

    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: Windows, runner_index):
        atl = new_book.runners[runner_index].ex.available_to_lay
        atb = new_book.runners[runner_index].ex.available_to_back

        if atl and atb:
            back = sum([x['size'] for x in atb[:self.wom_ticks]])
            lay = sum([x['size'] for x in atl[:self.wom_ticks]])
            return lay - back
        else:
            return None


@register_feature
class RunnerFeatureTradedDiff(RunnerFeatureWindowBase):
    """Difference in total traded runner volume in the last 'window_s' seconds"""

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorTradedVolumeLadder', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        try:
            return self.window['tv_diff_totals'].get(self.selection_id, None)
        except KeyError as e:
            raise BetfairFeatureException(f'error getting window attribute "tv_diff_totals"\n{e}')


@register_feature
class RunnerFeatureBestBack(RunnerFeatureBase):
    """Best available back price of runner"""

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        return best_price(new_book.runners[runner_index].ex.available_to_back)


@register_feature
class RunnerFeatureBestLay(RunnerFeatureBase):
    """
    Best available lay price of runner
    """

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        return best_price(new_book.runners[runner_index].ex.available_to_lay)


@register_feature
class RunnerFeatureLadderSpread(RunnerFeatureBase):
    """
    tick spread between best lay and best back - defaults to 1000 if cannot find best back or lay
    """
    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        best_lay = best_price(new_book.runners[runner_index].ex.available_to_lay)
        best_back = best_price(new_book.runners[runner_index].ex.available_to_back)

        if best_lay and best_back:
            return tick_spread(best_back, best_lay, check_values=False)
        else:
            return len(LTICKS_DECODED)


@register_feature
class RunnerFeatureBackLadder(RunnerFeatureBase):
    """
    best available price-sizes on back side within specified number of elements of best price
    """

    def __init__(self, n_elements, *args, **kwargs):
        self.n_elements = n_elements
        super().__init__(*args, **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):
        return new_book.runners[runner_index].ex.available_to_back[:self.n_elements]


@register_feature
class RunnerFeatureLayLadder(RunnerFeatureBase):
    """
    best available price-sizes on lay side within specified number of elements of best price
    """

    def __init__(self, n_elements, *args, **kwargs):
        self.n_elements = n_elements
        super().__init__(*args, **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):
        return new_book.runners[runner_index].ex.available_to_lay[:self.n_elements]


@register_feature
class RunnerFeatureSub(RunnerFeatureBase):
    """
    feature that must be used as a sub-feature to existing feature
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if kwargs.get('parent') is None:
            raise BetfairFeatureException(f'sub-feature has not received "parent" argument')


@register_feature
class RunnerFeatureSubDelayer(RunnerFeatureSub):
    """
    delay a parent feature by x number of seconds
    """

    def __init__(self, delay_seconds, *args, **kwargs):
        self.delay_seconds = delay_seconds
        self.delay_index = 0
        super().__init__(*args, **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        t = new_book.publish_time
        while (self.delay_index + 1) < len(self.parent.processed_vals) and \
                (t - self.parent.dts[self.delay_index + 1]).total_seconds() > self.delay_seconds:
            self.delay_index += 1

        if len(self.parent.processed_vals):
            return self.parent.processed_vals[self.delay_index]


@register_feature
class RunnerFeatureSubConstDelayer(RunnerFeatureSub):
    """
    get last parent feature value that has held its value without changing for x number of seconds
    """

    def __init__(self, hold_seconds, *args, **kwargs):
        self.hold_seconds = hold_seconds
        self.value_timestamp: datetime = datetime.now()
        self.parent_previous = None
        self.hold_value = None
        super().__init__(*args, **kwargs)

    def race_initializer(
            self,
            selection_id: int,
            first_book: MarketBook,
            windows: Windows):
        self.value_timestamp = first_book.publish_time

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        parent_current = self.parent.last_value()
        if self.parent_previous is None:
            self.parent_previous = parent_current

        if self.parent_previous is not None and parent_current is not None:
            if self.parent_previous != parent_current:
                self.value_timestamp = new_book.publish_time

            if (new_book.publish_time - self.value_timestamp).total_seconds() >= self.hold_seconds:
                self.hold_value = parent_current

        self.parent_previous = parent_current
        return self.hold_value


@register_feature
class RunnerFeatureSubLastValue(RunnerFeatureSub):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # store parent active value (until change)
        self.active_value = None

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        # check parent value list not empty
        if len(self.parent.processed_vals):

            # get most recent value from parent
            current_value = self.parent.processed_vals[-1]

            # check if active value is None
            if self.active_value is None:

                # first initialisation, just use value dont check for change
                self.active_value = current_value
                return current_value

            # check if current parent value is different from stored active value
            elif current_value != self.active_value:

                # stored active value is now previous value
                previous_value = self.active_value

                # update active value
                self.active_value = current_value

                # return previous state value
                return previous_value


@register_feature
class RunnerFeatureTVTotal(RunnerFeatureBase):
    """
    total traded volume of runner
    """
    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):
        return traded_runner_vol(new_book.runners[runner_index])


@register_feature
class RunnerFeatureSubRegression(RunnerFeatureSub):

    """
    Perform regressions on a runner values as a sub-feature
    - regression_preprocessor: apply pre-processor to feature values before performing linear regression (select from
    RunnerFeatureValueProcessors)
    """

    def __init__(
            self,
            element_count,
            regression_preprocessor: str = 'value_processor_identity',
            regression_preprocessor_args: dict = None,
            *args,
            **kwargs):
        """

        Parameters
        ----------
        element_count : number of elements at which to perform regression across
        regression_preprocessor : name of preprocessor function to use
        regression_preprocessor_args : kwargs passed to preprocessor function constructor
        args :
        kwargs :
        """
        super().__init__(
            *args,
            **kwargs,
        )
        self.element_count = element_count

        pre_kwargs = regression_preprocessor_args or {}
        self.regression_preprocessor = RunnerFeatureValueProcessors.get_processor(regression_preprocessor)(
            **pre_kwargs
        )

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: Windows,
            runner_index):

        dts = self.parent.dts[-self.element_count:]
        x = [(x - new_book.publish_time).total_seconds() for x in dts]
        y = self.parent.processed_vals[-self.element_count:]

        if not x or not y or len(x) != len(y):
            return None

        if len(x) < self.element_count:
            return None

        y_processed = [self.regression_preprocessor(v, y, dts) for v in y]
        X = np.expand_dims(x, -1)
        reg = LinearRegression().fit(X, y_processed)

        if len(reg.coef_) == 1:

            return {
                    'gradient': reg.coef_[0],
                    'rsquared': reg.score(X, y_processed)
                }

        return None

    def computation_buffer_seconds(self) -> int:
        if not self.parent.periodic_ms:
            active_logger.warning(f'regression sub feature expected parent to have periodic ms')
            return 0
        else:
            return int((self.parent.periodic_ms * self.element_count) / 1000)

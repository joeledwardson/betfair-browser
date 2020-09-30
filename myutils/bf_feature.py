from betfairlightweight.resources.bettingresources import MarketBook
from myutils import betting, bf_window
import numpy as np
from typing import List, Dict
import statsmodels.api as sm
import operator
import statistics
from datetime import datetime, timedelta


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
        """return same value"""
        def inner(value, values, datetimes):
            return value
        return inner

    @staticmethod
    def value_processor_moving_average(n_entries):
        """moving average over `n_entries`"""
        def inner(value, values, datetimes):
            return statistics.mean(values[-n_entries:])
        return inner

    @staticmethod
    def value_processor_invert():
        """get 1/value"""
        def inner(value, values, datetimes):
            return 1 / value
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
    """
    def __init__(
            self,
            value_processor: str = 'value_processor_identity',
            value_processor_args: dict = None,
            periodic_ms: int = None,
            periodic_timestamps: bool = False,
            ):

        self.windows: bf_window.Windows = None
        self.selection_id: int = None

        self.values = []
        self.dts = []

        creator = RunnerFeatureValueProcessors.get_processor(value_processor)
        self.value_processor = creator(**(value_processor_args if value_processor_args else {}))

        self.processed_vals = []

        self.periodic_ms = periodic_ms
        self.periodic_timestamps = periodic_timestamps
        self.last_timestamp: datetime = None

    def race_initializer(
            self,
            selection_id: int,
            first_book: MarketBook,
            windows: bf_window.Windows):
        """initialize feature with first market book of race and selected runner"""

        self.last_timestamp = first_book.publish_time
        self.selection_id = selection_id
        self.windows = windows

    def process_runner(
            self, market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
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

                # if periodically timestamped flag specified, set timestamp to sampled time and increment
                if self.periodic_timestamps:
                    publish_time = self.last_timestamp
                    self.last_timestamp = self.last_timestamp + timedelta(milliseconds=self.periodic_ms)

        # if periodic update milliseconds not specified, update regardless
        else:
            update = True

        # if criteria for updating value not met the ignore
        if not update:
            return

        # add datetime, value and processed value to lists
        def send_update(publish_time):

            # get feature value, ignore if None
            value = self.runner_update(market_list, new_book, windows, runner_index)
            if value is None:
                return

            # add raw value and timestamp to lists
            self.dts.append(publish_time)
            self.values.append(value)

            # compute value processor on raw value
            processed = self.value_processor(value, self.values, self.dts)

            # add processed value
            self.processed_vals.append(processed)

        send_update(publish_time)

        # if data is sampled and more than one sample time has elapsed, fill forwards until time is met
        if self.periodic_timestamps:
            while self.last_timestamp <= new_book.publish_time:
                self.last_timestamp = self.last_timestamp + timedelta(milliseconds=self.periodic_ms)
                send_update(self.last_timestamp)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):
        """
        implement this function to return feature value from new market book received
        return None if do not want value to be stored
        """
        raise NotImplementedError

    def get_plotly_data(self):
        """get feature data in list of plotly form dicts, where 'x' is timestamps and 'y' are feature values"""
        return [{
            'x': self.dts,
            'y': self.processed_vals
        }]


class RunnerFeatureWindowBase(RunnerFeatureBase):
    """
    base feature utilizing a window function (see bf_window.Windows)

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
            windows: bf_window.Windows):
        """
        add window of specified number of seconds to Windows instance and add specified window function when first
        market book received
        """

        super().race_initializer(selection_id, first_book, windows)
        self.window = windows.add_window(self.window_s)
        windows.add_function(self.window_s, self.window_function)


class RunnerFeatureTradedWindowMin(RunnerFeatureWindowBase):
    """Minimum of recent traded prices in last 'window_s' seconds"""

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorTradedVolumeLadder', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        prices = [tv['price'] for tv in self.window['tv_diff_ladder'][self.selection_id]]
        return min(prices) if prices else None


class RunnerFeatureTradedWindowMax(RunnerFeatureWindowBase):
    """Maximum of recent traded prices in last 'window_s' seconds"""

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorTradedVolumeLadder', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        prices = [tv['price'] for tv in self.window['tv_diff_ladder'][self.selection_id]]
        return max(prices) if prices else None


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
            windows: bf_window.Windows,
            runner_index):

        # best back price on current record
        best_back = betting.best_price(new_book.runners[runner_index].ex.available_to_back)

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


class RunnerFeatureLTP(RunnerFeatureBase):
    """Last traded price of runner"""
    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):
        return new_book.runners[runner_index].last_price_traded


class RunnerFeatureWOM(RunnerFeatureBase):
    """
    Weight of money (difference of available-to-lay to available-to-back)

    applied to `wom_ticks` number of ticks on BACK and LAY sides of the book
    """

    def __init__(self, wom_ticks, **kwargs):
        super().__init__(**kwargs)
        self.wom_ticks = wom_ticks

    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        atl = new_book.runners[runner_index].ex.available_to_lay
        atb = new_book.runners[runner_index].ex.available_to_back

        if atl and atb:
            back = sum([x['size'] for x in atb[:self.wom_ticks]])
            lay = sum([x['size'] for x in atl[:self.wom_ticks]])
            return lay - back
        else:
            return None


class RunnerFeatureTradedDiff(RunnerFeatureWindowBase):
    """Difference in total traded runner volume in the last 'window_s' seconds"""

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorTradedVolumeLadder', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        try:
            return self.window['tv_diff_totals'].get(self.selection_id, None)
        except KeyError as e:
            raise BetfairFeatureException(f'error getting window attribute "tv_diff_totals"\n{e}')


class RunnerFeatureBestBack(RunnerFeatureBase):
    """Best available back price of runner"""

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        return betting.best_price(new_book.runners[runner_index].ex.available_to_back)


class RunnerFeatureBestLay(RunnerFeatureBase):
    """Best available lay price of runner"""

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        return betting.best_price(new_book.runners[runner_index].ex.available_to_lay)


class RunnerFeatureRegression(RunnerFeatureWindowBase):
    """
    Perform regressions on a runner values from a window

    Special sub-set of window processors is `WindowProcessorFeatureBase`, where the key for values stored in the
    window is kept in `window_var` which is used to retrieve feature values from window

    - window_function: window function, must be derived from WindowProcessorFeatureBase
    - regression_seconds: number of seconds up to current record in which to apply regression
    - regression_strength_filter: minimum r-squared required to store regression
    - regression_preprocessor: apply pre-processor to feature values before performing linear regression (select from
    RunnerFeatureValueProcessors)
    - regression_postprocessor: apply post-processor to linear regression to convert back to feature values (select
    from RunnerFeatureValueProcessors)
    """

    def get_plotly_data(self):
        """Return list of regression results"""
        return self.values

    def __init__(
            self,
            window_function: str,
            regressions_seconds,
            regression_strength_filter=0,
            regression_gradient_filter=0,
            regression_preprocessor: str = 'value_processor_identity',
            regression_postprocessor: str = 'value_processor_identity',
            **kwargs):
        super().__init__(
            window_s=regressions_seconds,
            window_function=window_function,
            **kwargs
        )
        self.window_attr_name = None
        self.regression_strength_filter = regression_strength_filter
        self.regression_gradient_filter = regression_gradient_filter
        self.regression_preprocessor = RunnerFeatureValueProcessors.get_processor(regression_preprocessor)()
        self.regression_postprocessor = RunnerFeatureValueProcessors.get_processor(regression_postprocessor)()
        self.comparator = operator.gt if regression_gradient_filter >= 0 else operator.le

    def race_initializer(
            self,
            selection_id: int,
            first_book: MarketBook,
            windows: bf_window.Windows):

        super().race_initializer(selection_id, first_book, windows)

        # get the key for window values according to window function, use to retrieve values
        self.window_attr_name = windows.FUNCTIONS[self.window_function].window_var

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        dat = self.window[self.window_attr_name][self.selection_id]
        dts = dat['dts'].copy(),  # stop making hard reference
        x = [(x - new_book.publish_time).total_seconds() for x in dat['dts']]
        y = dat['values']

        if not y or not x:
            return None

        y_processed = [self.regression_preprocessor(v, y, dts) for v in y]

        X = np.column_stack([x])
        X = sm.add_constant(X)

        mod_wls = sm.WLS(y_processed, X)
        res_wls = mod_wls.fit()
        y_pred = res_wls.predict()
        y_pred = [self.regression_postprocessor(v, y_pred, dts) for v in y_pred]

        # TODO - incorporate regreesion postprocessor to predicted results, but dont want to calculate here is it is
        #  not required in real time, only for plotting
        if self.comparator(res_wls.params[1], self.regression_gradient_filter) and abs(
                res_wls.rsquared) >= self.regression_strength_filter:
            return {
                'dts': dat['dts'].copy(),  # stop making hard reference
                'predicted': y_pred,
                'params': res_wls.params,
                'rsquared': res_wls.rsquared
            }

        return None


def get_default_features_config(
        wom_ticks=5,
        ltp_window_s=40,
        ltp_periodic_ms=200,
        ltp_moving_average_entries=10,
        ltp_diff_s=2,
        regression_seconds=2,
        regression_strength_filter=0.1,
        regression_gradient_filter=0.003,
        regression_update_ms=200,
) -> Dict[str, Dict]:
    """
    Get a dict of default runner features, where each entry is a dictionary of:
    - key: feature usage name
    - value: dict of
        - 'name': class name of feature
        - 'kwargs': dict of constructor arguments used when creating feature
    """

    return {

        'best back': {
            'name': 'RunnerFeatureBestBack',
        },

        'best lay': {
            'name': 'RunnerFeatureBestLay',
        },

        'wom': {
            'name': 'RunnerFeatureWOM',
            'kwargs': {
                'wom_ticks': wom_ticks
            },
        },

        'ltp min': {
            'name': 'RunnerFeatureTradedWindowMin',
            'kwargs': {
                'periodic_ms': ltp_periodic_ms,
                'window_s': ltp_window_s,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': ltp_moving_average_entries
                },
            }
        },

        'ltp max': {
            'name': 'RunnerFeatureTradedWindowMax',
            'kwargs': {
                'periodic_ms': ltp_periodic_ms,
                'window_s': ltp_window_s,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': ltp_moving_average_entries
                },
            }
        },

        'ltp diff': {
            'name': 'RunnerFeatureTradedDiff',
            'kwargs': {
                'window_s': ltp_diff_s,
            }
        },

        'book split': {
            'name': 'RunnerFeatureBookSplitWindow',
            'kwargs': {
                'window_s': ltp_window_s,
            },
        },

        # put LTP last so it shows up above LTP max/min when plotting
        'ltp': {
            'name': 'RunnerFeatureLTP',
        },

        'best back regression': {
            'name': 'RunnerFeatureRegression',
            'kwargs': {
                'periodic_ms': regression_update_ms,
                'window_function': 'WindowProcessorBestBack',
                'regressions_seconds': regression_seconds,
                'regression_strength_filter': regression_strength_filter,
                'regression_gradient_filter': regression_gradient_filter,
                'regression_preprocessor': 'value_processor_invert',
                'regression_postprocessor': 'value_processor_invert',
            },
        },

        'best lay regression': {
            'name': 'RunnerFeatureRegression',
            'kwargs':  {
                'periodic_ms': regression_update_ms,
                'window_function': 'WindowProcessorBestLay',
                'regressions_seconds': regression_seconds,
                'regression_strength_filter': regression_strength_filter,
                'regression_gradient_filter': regression_gradient_filter * -1,
                'regression_preprocessor': 'value_processor_invert',
                'regression_postprocessor': 'value_processor_invert',
            },
        },
    }


def generate_features(
        selection_id: int,
        book: MarketBook,
        windows: bf_window.Windows,
        features_config: dict,
) -> Dict[str, RunnerFeatureBase]:
    """
    create dictionary of features based on a dictionary of `features_config`,
    - key: feature usage name
    - value: dict of
        - 'name': class name of feature
        - 'kwargs': dict of constructor arguments used when creating feature
    """
    features = dict()
    for name, conf in features_config.items():
        feature_class = globals()[conf['name']]
        features[name] = feature_class(**conf.get('kwargs', {}))
        features[name].race_initializer(selection_id, book, windows)
    return features


# def get_default_features(
#         selection_id,
#         book: MarketBook,
#         windows: bf_window.Windows,
#         **kwargs) -> Dict[str, RunnerFeatureBase]:
#
#     features_config = get_default_features_config(**kwargs)
#     features: Dict[str, RunnerFeatureBase] = {}
#     for name, conf in features_config.items():
#         feature_class = globals()[conf['name']]
#         features[name] = feature_class(**conf.get('kwargs', {}))
#         features[name].race_initializer(selection_id, book, windows)
#     return features

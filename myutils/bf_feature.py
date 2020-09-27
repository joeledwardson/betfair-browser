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
    @staticmethod
    def value_processor_identity():
        def inner(value, values, datetimes):
            return value
        return inner

    @staticmethod
    def value_processor_moving_average(n_entries):
        def inner(value, values, datetimes):
            return statistics.mean(values[-n_entries:])
        return inner

    @staticmethod
    def value_processor_invert():
        def inner(value, values, datetimes):
            return 1 / value
        return inner

    @classmethod
    def get_processor(cls, name):
        if name not in cls.__dict__:
            raise BetfairFeatureException(f'"{name}" not found in processors')
        else:
            return getattr(cls, name)

# base class for runner features
class RunnerFeatureBase:

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

        self.last_timestamp = first_book.publish_time
        self.selection_id = selection_id
        self.windows = windows

    def process_runner(
            self, market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

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


    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        raise NotImplementedError

    def get_plotly_data(self):
        return [{
            'x': self.dts,
            'y': self.processed_vals
        }]


# base feature utilizing a window function, where 'window_s' is the width in seconds of the window, and the window
# dict is stored in 'self.window'
class RunnerFeatureWindowBase(RunnerFeatureBase):
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

        super().race_initializer(selection_id, first_book, windows)
        self.window = windows.add_window(self.window_s)
        windows.add_function(self.window_s, self.window_function)


# minimum of recent traded prices in last 'window_s' seconds
class RunnerFeatureTradedWindowMin(RunnerFeatureWindowBase):

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


# maximum of recent traded prices in last 'window_s' seconds
class RunnerFeatureTradedWindowMax(RunnerFeatureWindowBase):

    def __init__(self, window_s, **kwargs):
        super().__init__(window_s, window_function='WindowProcessorTradedVolumeLadder', **kwargs)

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):



        prices = [tv['price'] for tv in self.window['tv_diff_ladder'][self.selection_id]]

        if self.selection_id == 35985191 and prices and abs(max(prices) - 3.7) < 0.01:
            my_debug_breakpoint=1

        return max(prices) if prices else None


# percentage of recent traded volume in the last 'window_s' seconds that is above current best back price
class RunnerFeatureBookSplitWindow(RunnerFeatureWindowBase):

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


# last traded price of runner
class RunnerFeatureLTP(RunnerFeatureBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        return new_book.runners[runner_index].last_price_traded


# weight of money, difference of available-to-lay to available-to-back
class RunnerFeatureWOM(RunnerFeatureBase):

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


# difference in total traded runner volume in the last 'window_s' seconds
class RunnerFeatureTradedDiff(RunnerFeatureWindowBase):

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


# best available back price of runner
class RunnerFeatureBestBack(RunnerFeatureBase):

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        return betting.best_price(new_book.runners[runner_index].ex.available_to_back)


# best available lay price of runner
class RunnerFeatureBestLay(RunnerFeatureBase):

    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):

        return betting.best_price(new_book.runners[runner_index].ex.available_to_lay)


# perform regressions on a feature
class RunnerFeatureRegression(RunnerFeatureWindowBase):

    # return list of regression results
    def get_plotly_data(self):
        return self.values

    def __init__(
            self,
            window_function: str,  # window function, must be derived from WindowProcessorFeatureBase
            regressions_seconds,
            regression_strength_filter=0,
            regression_gradient_filter=0,
            regression_preprocessor: str = 'value_processor_identity',  # convert values bf linear regression is
            # performed
            regression_postprocessor: str = 'value_processor_identity',  # convert predicted linear
            # regression values back to normal values
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
        self.window_attr_name = windows.FUNCTIONS[self.window_function].window_var

    # default of returning values, storing them with 'self.dts' etc is not valid as all info is encapsulated in
    # 'self.values'
    # def process_runner(
    #         self, market_list: List[MarketBook],
    #         new_book: MarketBook,
    #         windows: bf_window.Windows,
    #         runner_index):
    #     pass

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


# get dict of for default runner features
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


def get_default_features(
        selection_id,
        book: MarketBook,
        windows: bf_window.Windows,
        **kwargs) -> Dict[str, RunnerFeatureBase]:

    features_config = get_default_features_config(**kwargs)
    features: Dict[str, RunnerFeatureBase] = {}
    for name, conf in features_config.items():
        feature_class = globals()[conf['name']]
        features[name] = feature_class(**conf.get('kwargs', {}))
        features[name].race_initializer(selection_id, book, windows)
    return features

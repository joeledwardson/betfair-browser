from betfairlightweight.resources.bettingresources import MarketBook
from myutils import betting, bf_window
import numpy as np
from typing import List
import statsmodels.api as sm
import operator
import statistics


def get_plotly_vals(feature):
    return [{
        'x': feature.dts,
        'y': feature.processed_vals
    }]


def default_value_processor(value, feature):
    return value


def moving_average_processor(n_entries):
    def inner(value, feature):
        return statistics.mean(feature.values[-n_entries:])

    return inner


# base class for runner features
class RunnerFeatureBase:

    def __init__(self,
                 selection_id,
                 processed_vals_init=[],
                 value_processor=default_value_processor,
                 data_getter=get_plotly_vals):

        self.selection_id = selection_id
        self.values = []
        self.dts = []
        self.processed_vals = processed_vals_init.copy()  # create new list object
        self.value_processor = value_processor
        self.data_getter = data_getter

    def process_runner(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        value = self.runner_update(market_list, new_book, windows, runner_index)
        if value:
            self.dts.append(new_book.publish_time)
            self.values.append(value)
            processed = self.value_processor(value, self)
            self.processed_vals.append(processed)
            if len(self.values) != len(self.processed_vals):
                raise Exception(
                    f'Length of values {len(self.values)} different to processed values {len(self.processed_vals)}')

    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        raise NotImplementedError

    def get_data(self):
        return self.data_getter(self)


# base feature utilizing a window function, where 'window_s' is the width in seconds of the window, and the window
# dict is stored in 'self.window'
class RunnerFeatureTradedWindowBase(RunnerFeatureBase):
    def __init__(
            self,
            selection_id,
            window_s,
            windows: bf_window.Windows,
            window_function='WindowProcessorTradedVolumeLadder',
            **kwargs
    ):
        super().__init__(selection_id, **kwargs)
        self.window_s = window_s
        self.window = windows.add_window(window_s)
        windows.add_function(window_s, window_function)


# minimum of recent traded prices in last 'window_s' seconds
class RunnerFeatureTradedWindowMin(RunnerFeatureTradedWindowBase):
    def runner_update(
            self,
            market_list: List[MarketBook],
            new_book: MarketBook,
            windows: bf_window.Windows,
            runner_index):
        prices = [tv['price'] for tv in self.window['tv_diff_ladder'][self.selection_id]]
        return min(prices) if prices else None


# maximum of recent traded prices in last 'window_s' seconds
class RunnerFeatureTradedWindowMax(RunnerFeatureTradedWindowBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        prices = [tv['price'] for tv in self.window['tv_diff_ladder'][self.selection_id]]
        return max(prices) if prices else None


# percentage of recent traded volume in the last 'window_s' seconds that is above current best back price
class RunnerFeatureBookSplitWindow(RunnerFeatureTradedWindowBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        best_back = betting.best_price(new_book.runners[runner_index].ex.available_to_back)
        if best_back:
            ladder_diffs = self.window['tv_diff_ladder'][self.selection_id]
            total_diff = self.window['tv_diff_totals'][self.selection_id]
            back_diff = sum([x['size'] for x in ladder_diffs if x['price'] > best_back])
            if total_diff:
                return back_diff / total_diff

        return None


# last traded price of runner
class RunnerFeatureLTP(RunnerFeatureBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        return new_book.runners[runner_index].last_price_traded


# weight of money, difference of available-to-lay to available-to-back
class RunnerFeatureWOM(RunnerFeatureBase):

    def __init__(self, selection_id, wom_ticks, **kwargs):
        super().__init__(selection_id, **kwargs)
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
class RunnerFeatureTradedDiff(RunnerFeatureTradedWindowBase):
    def __init__(
            self,
            selection_id,
            window_s,
            windows: bf_window.Windows,
            **kwargs):
        super().__init__(
            selection_id,
            window_s,
            windows,
            window_function='WindowProcessorTradedVolumeLadder',
            **kwargs)

    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        return self.window['tv_diff_totals'].get(self.selection_id, None)


# best available back price of runner
class RunnerFeatureBestBack(RunnerFeatureBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        atb = new_book.runners[runner_index].ex.available_to_back
        if atb:
            return atb[0]['price']
        else:
            return None


# best available lay price of runner
class RunnerFeatureBestLay(RunnerFeatureBase):
    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        atl = new_book.runners[runner_index].ex.available_to_lay
        if atl:
            return atl[0]['price']
        else:
            return None


# return list of regression results
def get_regression_data(feature: RunnerFeatureBase):
    return feature.values


# perform regressions on a feature
class RunnerFeatureRegression(RunnerFeatureTradedWindowBase):
    def __init__(
            self,
            selection_id,
            windows: bf_window.Windows,
            window_function: str,
            regressions_seconds,
            regression_strength_filter=0,
            regression_gradient_filter=0,
            regression_preprocessor=lambda v: v,  # convert values before linear regression is performed
            regression_postprocessor=lambda v: v,  # convert predicted linear regression values back to normal values
            **kwargs):
        super().__init__(
            selection_id,
            window_s=regressions_seconds,
            windows=windows,
            window_function=window_function,
            data_getter=get_regression_data,
            **kwargs
        )
        self.window_attr_name = windows.FUNCTIONS[window_function].window_var
        self.regression_strength_filter = regression_strength_filter
        self.regression_gradient_filter = regression_gradient_filter
        self.regression_preprocessor = regression_preprocessor
        self.regression_postprocessor = regression_postprocessor
        self.comparator = operator.gt if regression_gradient_filter >= 0 else operator.le

    def runner_update(self, market_list: List[MarketBook], new_book: MarketBook, windows: bf_window.Windows, runner_index):
        dat = self.window[self.window_attr_name][self.selection_id]
        x = [(x - new_book.publish_time).total_seconds() for x in dat['dts']]
        y = dat['values']

        if not y or not x:
            return None

        y_processed = [self.regression_preprocessor(v) for v in y]

        X = np.column_stack([x])
        X = sm.add_constant(X)

        mod_wls = sm.WLS(y_processed, X)
        res_wls = mod_wls.fit()
        y_pred = res_wls.predict()
        y_pred = [self.regression_postprocessor(v) for v in y_pred]

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

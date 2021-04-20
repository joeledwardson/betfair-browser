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
from myutils.myregistrar import MyRegistrar
import statistics
from datetime import datetime
from typing import List, Callable, Dict
import numpy as np
from mytrading.process.ticks.ticks import closest_tick

runner_feature_value_processors = MyRegistrar()


def get_feature_processor(name, kwargs):
    creator = runner_feature_value_processors[name]
    return creator(**(kwargs or {}))


def get_feature_processors(config: List[Dict]) -> List[Callable]:
    assert (type(config) is list)
    return [
        get_feature_processor(p['name'], p.get('kwargs', {}))
        for p in config
    ]


@runner_feature_value_processors.register_element
def value_processor_identity():
    """
    return same value
    """
    def inner(value, values: List, datetimes: List[datetime]):
        return value
    return inner


@runner_feature_value_processors.register_element
def value_processor_moving_average(n_entries):
    """
    moving average over `n_entries`
    """
    def inner(value, values: List, datetimes: List[datetime]):
        return statistics.mean(values[-n_entries:])
    return inner


@runner_feature_value_processors.register_element
def value_processor_invert():
    """
    get 1/value unless value is 0 where return 0
    """
    def inner(value, values: List, datetimes: List[datetime]):
        return 1 / value if value != 0 else 0
    return inner


@runner_feature_value_processors.register_element
def value_processor_to_tick():
    """
    convert a numeric value to tick
    """
    def inner(value, values: List, datetimes: List[datetime]):
        return closest_tick(value, return_index=True)
    return inner


@runner_feature_value_processors.register_element
def value_processor_max():
    """
    get the max value from the list
    """
    def inner(value, values: List, datetimes: List[datetime]):
        return max(values)
    return inner


@runner_feature_value_processors.register_element
def value_processor_min():
    """
    get the minimum value from the list
    """
    def inner(value, values: List, datetimes: List[datetime]):
        return min(values)
    return inner


@runner_feature_value_processors.register_element
def value_processor_max_dif():
    """
    get the max value from the list
    """
    def inner(value, values: List, datetimes: List[datetime]):
        if len(values) >= 2:
            return max(abs(np.diff(values)).tolist())
        else:
            return 0
    return inner


@runner_feature_value_processors.register_element
def value_processor_sum():
    """
    sum values in list
    """
    def inner(value, values: List, datetimes: List[datetime]):
        return sum(values)
    return inner

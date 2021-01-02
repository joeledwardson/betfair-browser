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
from typing import List

runner_feature_value_processors = MyRegistrar()


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
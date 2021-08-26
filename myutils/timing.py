import functools
import time
from datetime import timedelta
import logging
import pandas as pd
from typing import List, Dict
from .exceptions import TimingException



active_logger = logging.getLogger(__name__)
_function_timings = {}


def decorator_timer(func):
    """
    log the runtime of the decorated function
    """

    # preserve function information
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        # gets time in seconds (with decimal places)
        start_time = time.perf_counter()

        # execute function and store output
        val = func(*args, **kwargs)

        # get time after function complete
        end_time = time.perf_counter()

        # print time to execute function
        elapsed_time = end_time - start_time
        active_logger.info(f'Finished {func.__name__} in {elapsed_time:.4f} seconds')

        return val

    return wrapper_timer


def timing_register_attr(name_attr):
    """
    register a class method, whose name at runtime is determined by
    - first component is attribute specified by `name_attr`
    - second component is function name

    e.g. the following below would yield to key in timing registrar of 'hello.timed_function'
    class A:
        c='hello'
        @timing_register_attr(name_attr='c')
        def timed_function():
            # some stuff

    """

    def outer(method):

        # preserve function information
        @functools.wraps(method)
        def inner(self, *args, **kwargs):

            # gets time in seconds (with decimal places)
            start_time = time.perf_counter()

            # execute function and store output
            val = method(self, *args, **kwargs)

            # get time after function complete
            end_time = time.perf_counter()

            # add execution time to list
            elapsed_time = end_time - start_time

            # use object name with method name for key
            nm = getattr(self, name_attr) + '.' + method.__name__
            if nm not in _function_timings:
                _function_timings[nm] = list()
            _function_timings[nm].append(timedelta(seconds=elapsed_time))

            return val

        return inner

    return outer


def timing_register(func):
    """
    register a function for execution times to be logged, using function name as key to register
    """
    # create empty list for runtimes
    _function_timings[func.__name__] = []

    # preserve function information
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):

        # gets time in seconds (with decimal places)
        start_time = time.perf_counter()

        # execute function and store output
        val = func(*args, **kwargs)

        # get time after function complete
        end_time = time.perf_counter()

        # add execution time to list
        elapsed_time = end_time - start_time
        _function_timings[func.__name__].append(timedelta(seconds=elapsed_time))

        return val

    return wrapper_timer


def timing_register_method(func):
    """
    register a class method for execution times to be logged
    """

    # preserve function information
    @functools.wraps(func)
    def wrapper_timer(self, *args, **kwargs):

        # gets time in seconds (with decimal places)
        start_time = time.perf_counter()

        # execute function and store output
        val = func(self, *args, **kwargs)

        # get time after function complete
        end_time = time.perf_counter()

        # add execution time to list
        elapsed_time = end_time - start_time

        name = self.__class__.__name__ + '.' + func.__name__
        if name not in _function_timings:
            _function_timings[name] = []
        _function_timings[name].append(timedelta(seconds=elapsed_time))

        return val

    return wrapper_timer


def get_function_timings(func_name) -> pd.Series:
    """
    get series of timedeltas for execution time each time function was run
    """
    return pd.Series(_function_timings[func_name])


def get_timed_functions() -> List[str]:
    """
    get list of function names who are being tracked for timing
    """
    return list(_function_timings.keys())


def print_timings_summary() -> None:
    """
    plot timings results for each timed function
    """
    for f in get_timed_functions():
        print(f'printing function timings for "{f}"')
        d = get_function_timings(f).describe()
        for name, val in d.iteritems():
            print(f'{name:5}: {val}')
        print('\n')


def get_timings_summary() -> List[Dict]:
    """
    get a list of dictionaries with function timings information:
    'Function' is function name
    'Count' is number of times function was recorded
    'Mean' is mean of timings as timedelta object
    'Min' is minimum time as timedelta object
    'Max' is maximum time as timedelta object
    """
    results = []
    for k, v in _function_timings.items():
        if v:
            results.append({
                'function': k,
                'count': len(v),
                'mean': sum(v, timedelta())/len(v),
                'min': min(v),
                'max': max(v),
            })
    return results


def clear_timing_function(func_name: str) -> None:
    """
    empty specific timed function
    """
    _function_timings[func_name].clear()


def clear_timing_register() -> None:
    """
    empty lists of timed functions results
    """
    for k in _function_timings.keys():
        _function_timings[k].clear()



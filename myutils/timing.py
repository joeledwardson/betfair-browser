import functools
import time
from datetime import timedelta
import logging
import pandas as pd
from typing import List, Dict, Callable, Any, TypedDict, Optional
from .exceptions import TimingException
import copy


active_logger = logging.getLogger(__name__)


class TimingResult(TypedDict):
    function: str
    count: int
    mean: timedelta
    min: timedelta
    max: timedelta


class TimingRegistrar:
    def __init__(self, timings: Optional[Dict[str, List[timedelta]]] = None):
        self._function_timings: Dict[str, List[timedelta]] = timings or {}

    def log_result(self, elapsed_seconds: float, name: str) -> None:
        if name not in self._function_timings:
            self._function_timings[name] = []
        self._function_timings[name].append(timedelta(seconds=elapsed_seconds))

    def _call(self, f: Callable,  key: str, *args, **kwargs) -> Any:
        start_time = time.perf_counter()  # gets timestamp in seconds (with decimal places)
        val = f(*args, **kwargs)  # execute function and store output
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time  # compute time for function execution
        # use object name with method name for key
        if key not in self._function_timings:
            self._function_timings[key] = list()
        self._function_timings[key].append(timedelta(seconds=elapsed_time))
        return val

    def register_named_method(self, name_attr: str) -> Callable:
        """
        register a class method, whose name at runtime is determined by
        - first component is attribute specified by `name_attr`
        - second component is function name

        e.g. the following below would yield to key in timing registrar of 'hello.timed_function'
        reg = TimingRegistrar()
        class A:
            c='hello'
            @reg.register_named_method(name_attr='c')
            def timed_function():
                # some stuff

        """
        def outer(method: Callable):
            @functools.wraps(method)
            def inner(_self, *args, **kwargs):
                # use object name with method name for key
                key = getattr(_self, name_attr) + '.' + method.__name__
                return self._call(method, key, _self, *args, **kwargs)
            return inner
        return outer

    def register_method(self, func: Callable) -> Callable:
        """
        Register a class method for execution times to be logged

        Example below would register function calls to key 'A.hello'
        reg = TimingRegistrar()
        class A:
            @reg.register_method
            def hello(self):
                # do some stuff
        """
        @functools.wraps(func)
        def inner(_self, *args, **kwargs):
            key = _self.__class__.__name__ + '.' + func.__name__
            return self._call(inner, key, _self, *args, **kwargs)
        return inner

    def register_function(self, func: Callable) -> Callable:
        """
        Register a function for execution times to be logged, using function name as key to register

        The example below would register function timings to key 'hello'
        reg = TimingRegistrar()
        @reg.register_function
        def hello():
            # do some stuff
        """
        @functools.wraps(func)
        def inner(*args, **kwargs):
            return self._call(func, func.__name__, *args, **kwargs)
        return inner

    def _series(self, func_name: str) -> pd.Series:
        """
        get series of timedeltas for execution time each time function was run
        """
        return pd.Series(self._function_timings[func_name])

    def timed_functions(self) -> List[str]:
        """
        get list of function names who are being tracked for timing
        """
        return list(self._function_timings.keys())

    def get_timings_summary(self) -> List[Dict]:
        """
        get a list of dictionaries with function timings information:
        'Function' is function name
        'Count' is number of times function was recorded
        'Mean' is mean of timings as timedelta object
        'Min' is minimum time as timedelta object
        'Max' is maximum time as timedelta object
        """
        return [
            TimingResult(
                function=k,
                count=len(v),
                mean=sum(v, timedelta()) / len(v),
                min=min(v),
                max=max(v),
            ) for k, v in self._function_timings.items() if v
        ]

    def clear(self) -> None:
        """
        empty lists of timed functions results
        """
        self._function_timings = {}

    def items(self):
        return self._function_timings.items()
    def __contains__(self, item):
        return self._function_timings.__contains__(item)
    def __setitem__(self, key, value):
        return self._function_timings.__setitem__(key, value)
    def __getitem__(self, item):
        return self._function_timings.__getitem__(item)

    def __add__(self, other):
        result = TimingRegistrar(self._function_timings)
        for k, v in other.items():
            if k in result:
                result[k] += v
            else:
                result[k] = v
        return result


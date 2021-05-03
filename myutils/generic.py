import time
import datetime
import re
import json
import jsonpickle
import numpy
import logging
from typing import List, Dict
import functools
import os
import operator


class StateTracker:
    def __init__(self, init_value, comparator=operator.ne):
        self.value = init_value
        self.comparator = comparator

    def update(self, new_value) -> bool:
        old_value = self.value
        self.value = new_value
        return self.comparator(new_value, old_value)


def i_prev(i, increment=1):
    """
    i-1, clamped at minimum 0 (can specify 'increment' to values other than 1)
    """
    return max(i - increment, 0)


def i_next(i, n, increment=1):
    """
    i+1, clamped at maximum n-1 (can specify 'increment' to values other than 1)
    """
    return min(i + increment, n - 1)


def dict_sort(d: dict, key=lambda item: item[1]) -> Dict:
    """sort a dictionary items"""
    return {k: v for k, v in sorted(d.items(), key=key)}


def get_filepaths(target_path, file_pattern=None, dir_pattern=None):
    """
    get complete list of full file paths with a 'target_path' directory
    Can specify an optional 'file_pattern' regex to only match certain file names
    Can specify an optional 'dir_pattern' regex to match certain directory names
    """

    files = []

    for (dirpath, dirnames, filenames) in os.walk(target_path):
        for f in filenames:
            if file_pattern and not re.match(file_pattern, f):
                continue
            if dir_pattern:
                _, d = os.path.split(dirpath)
                if not re.match(dir_pattern, d):
                    continue
            files.append(os.path.join(dirpath, f))

    return files


def dgetattr(obj, name, is_dict=False):
    """
    get deep attribute
    operates the same as getattr(obj, name) but can use '.' for nested attributes
    e.g. dgetattr(my_object, 'a.b') would return value of my_object.a.b
    """
    atr = dict.__getitem__ if is_dict else getattr
    names = name.split('.')
    names = [obj] + names
    return functools.reduce(atr, names)


def dattr_name(deep_attr):
    """
    get deep attribute name
    e.g. dattr_name('my_object.a.b') would return 'b'
    """
    return re.match(r'(.*[.])?(.*)', deep_attr).groups()[1]


def get_index(object_list: [List, object], f):
    """
    get first index where single argument function 'f(o)' called on object 'o' in list of objects 'object_list' returns
    true
    otherwise return None
    """
    for i, o in enumerate(object_list):
        if f(o):
            return i
    else:
        return None


def get_object(object_list: [List, object], f):
    """
    get first object where single argument function 'f(o)' called on object 'o' in list of objects 'object_list' returns
    True
    otherwise return None
    """
    for i, o in enumerate(object_list):
        if f(o):
            return o
    else:
        return None


def milliseconds():
    """milliseconds sinch epoch"""
    return round(time.time()*1000)


def ms_to_datetime(timestamp_ms):
    return datetime.datetime.fromtimestamp(float(timestamp_ms)/1000)


def object_members(o):
    return [k for k in o.__dir__() if not re.match('^_', k) and not callable(getattr(o, k))]


def prettified_members(o, indent=4):
    """deep object with all members printed for dicts/classes"""

    # pickle into json (string) form
    pickled = jsonpickle.encode(o)

    # load back into object form (with subtrees for all object members)
    json_object = json.loads(pickled)

    # use json to convert to string but this time with indents
    return json.dumps(json_object, indent=indent)


def closest_value(array, value, return_index=False, round_down=False, round_up=False):
    """# get closest value in numpy array, specify return_index=True to return index instead of value"""

    # get index in reversed array of smallest distance to value
    index = abs(array - value).argmin()

    # round down if necessary
    if round_down and index > 0 and array[index] > value:
        index -= 1

    # round up if necessary
    if round_up and index < (len(array) - 1) and array[index] < value:
        index += 1

    if return_index:
        return int(index)  # return as regular integer
    else:
        # return value from reversed array
        return array[index]


def constructor_verify(value, object_type) -> bool:
    """Returns True if can create object from type"""
    try:
        object_type(value)
        return True
    except (ValueError, TypeError) as e:
        return False


def is_jsonable(x):
    """
    determine if data can be serialized
    """
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False


class Counter:
    def __init__(self, initial_value: int = 0):
        self.value: int = initial_value

    def inc(self) -> int:
        self.value += 1
        return self.value

    def __repr__(self):
        return self.value
import time
import datetime
import re
import json
import jsonpickle
import numpy
import logging
from typing import List
import functools
import os


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


def create_dirs(func):
    """
    Sample function wrapper that
    - assumes first function is file name
    - creates nested directories specified by first arg file name before running function
    """

    def wrapper(file_name, *args, **kwargs):
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        return func(file_name, *args, **kwargs)
    return wrapper


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


def dgetattr(obj, name):
    """
    get deep attribute
    operates the same as getattr(obj, name) but can use '.' for nested attributes
    e.g. dgetattr(my_object, 'a.b') would return value of my_object.a.b
    """
    names = name.split('.')
    names = [obj] + names
    return functools.reduce(getattr, names)


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


class StaticClass:
    def __init__(self):
        raise Exception('Static class only, instances not allowed')

def milliseconds():
    return round(time.time()*1000)


def ms_to_datetime(timestamp_ms):
    return datetime.datetime.fromtimestamp(float(timestamp_ms)/1000)


def object_members(o):
    return [k for k in o.__dir__() if not re.match('^_', k) and not callable(getattr(o, k))]


# deep object with all members printed for dicts/classes
def prettified_members(o, indent=4):

    # pickle into json (string) form
    pickled = jsonpickle.encode(o)

    # load back into object form (with subtrees for all object members)
    json_object = json.loads(pickled)

    # use json to convert to string but this time with indents
    return json.dumps(json_object, indent=indent)


# get closest value in numpy array, specify return_index=True to return index instead of value
def closest_value(array, value, return_index=False):

    # get reversed array (so that larger values are selected first when equidistant)
    # remember that indexing in numpy is like slicing (start, stop, step), so ::-1 just reverses the list
    reverse_array = numpy.sort(array)[::-1]

    # get index in reversed array of smallest distance to value
    index = abs(reverse_array - value).argmin()

    if return_index:
        return index
    else:
        # return value from reversed array
        return reverse_array[index]
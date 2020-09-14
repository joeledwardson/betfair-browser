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

# Sample function wrapper that
# - assumes first function is file name
# - creates nested directories specified by first arg file name before running function
def create_dirs(func):
    def wrapper(file_name, *args, **kwargs):
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        return func(file_name, *args, **kwargs)
    return wrapper

def get_filepaths(target_path, file_pattern, dir_pattern=None):
    files = []

    for (dirpath, dirnames, filenames) in os.walk(target_path):
        for f in filenames:
            if not re.match(file_pattern, f):
                continue
            if dir_pattern:
                _, d = os.path.split(dirpath)
                if not re.match(dir_pattern, d):
                    continue
            files.append(os.path.join(dirpath, f))


    return files


# deep get attr, can use '.' for nested attributes. e.g. dgetattr(my_object, 'a.b') would be for my_object.a.b
def dgetattr(obj, name):
    names = name.split('.')
    names = [obj] + names
    return functools.reduce(getattr, names)

def dattr_name(deep_attr):
    return re.match(r'(.*[.])?(.*)', deep_attr).groups()[1]

'''
get first index where single argument function 'f(o)' called on object 'o' in list of objects 'object_list' returns true
otherwise return None
'''
def get_index(object_list: [List, object], f):
    for i, o in enumerate(object_list):
        if f(o):
            return i
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


# get closest value in numpy array
def closest_value(array, value):

    # get reversed array (so that larger values are selected first when equidistant)
    # remember that indexing in numpy is like slicing (start, stop, step), so ::-1 just reverses the list
    reverse_array = numpy.sort(array)[::-1]

    # get index in reversed array of smallest distance to value
    index = abs(reverse_array - value).argmin()

    # return value from reversed array
    return reverse_array[index]
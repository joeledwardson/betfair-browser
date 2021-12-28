import time
import datetime
import re
import json
import jsonpickle
from typing import List
import functools


def flatten(x: List[List[any]]) -> List[any]:
    return [item for sublist in x for item in sublist]


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

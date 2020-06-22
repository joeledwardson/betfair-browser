import time
import datetime
import re
import json
import jsonpickle
import numpy

def milliseconds():
    return round(time.time()*1000)


def ms_to_datetime(timestamp_ms):
    return datetime.datetime.fromtimestamp(float(timestamp_ms)/1000)


def object_members(o):
    return [k for k in o.__dir__() if not re.match('^_', k)]


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


def testfunction(a, b):
    print(a)
from typing import Iterable


def is_dict_subset(x, y):
    """recursively determine if key value pairs in x are a subset of y"""
    for k, v in x.items():
        if k not in y:
            return False
        elif type(v) is dict:
            if not isinstance(y[k], Iterable):
                return False
            elif not is_dict_subset(v, y[k]):
                return False
        elif v != y[k]:
            return False
    return True


def dict_update(x: dict, y: Iterable):
    """recursively update key value pairs of y with x"""

    for k, v in x.items():

        if type(v) is not dict:
            # value is not dict
            y[k] = v
            continue

        # value is dict
        if k not in y:
            # value is dict & key not found in y
            y[k] = v
            continue

        # value is dict & key found in y
        if isinstance(y[k], Iterable):
            # value is dict & key found in y & value in y is iterable
            dict_update(v, y[k])
            continue

        # value is dict & key found in y & value in y is not iterable
        y[k] = v
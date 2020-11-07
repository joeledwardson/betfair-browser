import logging
from os import walk
from typing import List


def walk_first(top) -> (str, List, List):
    """
    get root, dirs & files
    """
    try:
        return next(iter(walk(top)))
    except StopIteration as e:
        logging.warning(f'failed to retrieve files from "{top}"')
        return '', [], []
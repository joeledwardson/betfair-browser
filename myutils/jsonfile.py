import json
import logging

active_logger = logging.getLogger(__name__)


def add_to_file(file_path, data, mode='a', indent=None):
    """
    add a serializable data object as a new line to a file
    """
    with open(file_path, mode=mode) as f:
        try:
            json_data = json.dumps(data, indent=indent)
        except TypeError as e:
            active_logger.critical(f'failed to serialise data writing to file: "{file_path}"\n{e}')
            return

        f.writelines([json_data + '\n'])


def read_file_lines(file_path):
    """
    get a list of de-serialized objects from each line in a file, return empty list on fail
    """
    with open(file_path) as f:
        lines = f.readlines()

    try:
        json_data = [json.loads(line) for line in lines]
        return json_data
    except TypeError as e:
        active_logger.critical(f'failed to load data from: "{file_path}"\n{e}')
        return []


def read_file_data(file_path):
    """
    read and parse string data from file, taking entire file as one string, return None on fail

    Parameters
    ----------
    file_path :

    Returns
    -------

    """
    with open(file_path) as f:
        data = f.read()
    try:
        json_data = json.loads(data)
        return json_data
    except TypeError as e:
        active_logger.critical(f'failed to load data from: "{file_path}"\n{e}')
        return None


def is_jsonable(x):
    """
    determine if data can be serialized
    """
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False



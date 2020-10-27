import json
import logging

active_logger = logging.getLogger(__name__)


def add_to_file(file_path, data, mode='a'):
    """
    add a serializable data object as a new line to a file
    """
    with open(file_path, mode=mode) as f:
        try:
            json_data = json.dumps(data)
        except TypeError as e:
            active_logger.critical(f'failed to serialise data writing to file: "{file_path}"\n{e}')
            return

        f.writelines([json_data + '\n'])


def read_file(file_path):
    """
    get a list of de-serialized objects from each line in a file
    """
    with open(file_path) as f:
        lines = f.readlines()

    try:
        json_data = [json.loads(line) for line in lines]
        return json_data
    except TypeError as e:
        active_logger.critical(f'failed to load data from: "{file_path}"\n{e}')
        return []


def is_jsonable(x):
    """
    determine if data can be serialized
    """
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False



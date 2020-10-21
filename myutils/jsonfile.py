import json


def add_to_file(file_path, data):
    """add a serializable data object as a new line to a file"""
    with open(file_path, mode='a') as f:
        f.writelines([json.dumps(data) + '\n'])


def read_file(file_path):
    """get a list of de-serialized objects from each line in a file"""
    with open(file_path) as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines]


def is_jsonable(x):
    """determine if data can be serialized"""
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False



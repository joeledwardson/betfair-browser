from . import generic, betting, timing
import importlib
from datetime import datetime


def reload_utils():
    for lib in [generic, betting, timing]:
        importlib.reload(lib)
    print(f'{datetime.now().strftime("%y-%m-%d %H-%M-%S")} - utils lib reloaded')
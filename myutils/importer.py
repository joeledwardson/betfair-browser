from . import generic, betting, mytiming
import importlib
from datetime import datetime


def reload_utils():
    for lib in [generic, betting, mytiming]:
        importlib.reload(lib)
    print(f'{datetime.now().strftime("%y-%m-%d %H-%M-%S")} - utils lib reloaded')
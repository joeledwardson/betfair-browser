import functools
import time
from datetime import datetime, timedelta


# decorating function to print time elapsed once complete
def decorator_timer(func):
    """Print the runtime of the decorated function"""

    # preserve function information
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        # gets time in seconds (with decimal places)
        start_time = time.perf_counter()

        # execute function and store output
        val = func(*args, **kwargs)

        # get time after function complete
        end_time = time.perf_counter()

        # print time to execute function
        elapsed_time = end_time - start_time
        print(f'Finished {func.__name__} in {elapsed_time:.4f} seconds')

        return val

    return wrapper_timer


class RepeatingTimer:
    def __init__(self, period_ms):
        self.timeDelta = timedelta(milliseconds=period_ms)
        self.timeStart = None
        self.nPulses = None
        self.reset()

    def reset(self):
        self.timeStart = datetime.now()
        self.nPulses = 0

    def get(self):
        new_pulse = self.timeStart + (self.timeDelta * (self.nPulses + 1))
        if datetime.now() >= new_pulse:
            self.nPulses += 1
            return True
        else:
            return False
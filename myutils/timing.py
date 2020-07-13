import functools
import time
from datetime import datetime, timedelta


class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class"""

class MyTimer:
    def __init__(self):
        self._running = False
        self._start_time = None
        self._elapsed_time = 0

    def start(self):
        if self._running is True:
            raise TimerError('Tried to start timer when already running')

        self._running = True
        self._start_time = time.perf_counter()

    def stop(self):
        if self._running is False:
            raise TimerError('Tried to stop timer when already running')

        self._running = False
        self._elapsed_time += (time.perf_counter() - self._start_time)

    def reset(self):
        if self._running is True:
            raise TimerError('Tried to reset timer when running')

        self._elapsed_time = 0.0

    def elapsed(self):
        if self._running is True:
            return self._elapsed_time + (time.perf_counter() - self._start_time)
        else:
            return self._elapsed_time

class TimeSimulator():
    def __init__(self):
        self._start_date = datetime.now()
        self._timer = MyTimer()
    def start(self):
        self._timer.start()
    def stop(self):
        self._timer.stop()
    def reset_start(self, start_date: datetime):

        # stop timer if running
        running = self._timer._running
        if running:
            self._timer.stop()

        # reset counter
        self._timer.reset()

        # update start date
        self._start_date = start_date

        # restart timer if was running
        if running:
            self._timer.start()

    def seconds_elapsed(self):
        return self._timer.elapsed()
    def current(self):
        return self._start_date + timedelta(seconds=self._timer.elapsed())


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
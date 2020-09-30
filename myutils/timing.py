import functools
import time
from datetime import datetime, timedelta
import pytz


class EdgeDetector:
    """
    detect when a boolean value changes from True to False and vice-versa comparing to previous-state value
    """
    def __init__(self, initial_value: bool):
        self._value: bool = initial_value
        self._previous: bool = initial_value
        self._rising: bool = False
        self._falling: bool = False

    def update(self, new_value) -> bool:
        """update value, return True if rising or falling edge"""
        self._previous = self._value
        self._value = new_value
        self._rising = self._value and not self._previous
        self._falling = self._previous and not self._value
        return self._rising or self._falling

    @property
    def current_value(self):
        return self._value

    @property
    def rising(self):
        return self._rising

    @property
    def falling(self):
        return self._falling


def format_timedelta(td: timedelta, fmt: str = '{h:02}:{m:02}:{s:02}') -> str:
    """
    format timedelta object with format spec
    valid format specifiers include
    - d: days
    - h: hours
    - m: minutes
    - s: seconds
    - ms: milliseconds
    """
    s = td.total_seconds()
    formatters = {
        'ms':   int(s * 1000) % 1000,
        's':    int(s) % 60,
        'm':    int(s / 60) % 60,
        'h':    int(s / (60 * 60)) % 24,
        'd':    int(s / (60 * 60 * 24))
    }
    return fmt.format(**formatters)


def time_info(dt: datetime) -> bool:
    """datetime contains time information"""
    return dt.hour != 0 or dt.minute != 0 or dt.second != 0 or dt.microsecond != 0


def localise(dt: datetime):
    """turn UTC datetime into London datetime with daylight savings"""
    return pytz.UTC.localize(dt).astimezone(pytz.timezone('Europe/London'))


def today(tz=None):
    """get datetime of today (no time info)"""
    now = datetime.now(tz)
    return datetime(year=now.year, month=now.month, day=now.day)


def tomorrow(tz=None):
    """get datetime of tomorrow (no time info)"""
    return today(tz) + timedelta(days=1)


class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class"""


class MyTimer:
    """
    timer that can be started and stopped, with elapsed property denoted time passed since start
    keeps track of total time elapsed whilst stopping and starting
    must not try to stop when already stopped, or start when already started
    """
    def __init__(self):
        self._running: bool = False
        self._start_time: float = 0
        self._elapsed_time: float = 0

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

    @property
    def elapsed(self):
        if self._running is True:
            return self._elapsed_time + (time.perf_counter() - self._start_time)
        else:
            return self._elapsed_time


# TODO - update this
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
    """get a True boolean value when calling get() every time period in milliseconds has elapsed"""
    def __init__(self, period_ms):
        self.timeDelta = timedelta(milliseconds=period_ms)
        self.timeStart = None
        self.nPulses = None
        self.reset()

    def reset(self):
        self.timeStart = datetime.now()
        self.nPulses = 0

    def get(self) -> bool:
        new_pulse = self.timeStart + (self.timeDelta * (self.nPulses + 1))
        if datetime.now() >= new_pulse:
            self.nPulses += 1
            return True
        else:
            return False


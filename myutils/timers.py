import time
from datetime import datetime, timedelta
from .exceptions import TimingException


class Timer:
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
            raise TimingException('Tried to start timer when already running')

        self._running = True
        self._start_time = time.perf_counter()

    def stop(self):
        if self._running is False:
            raise TimingException('Tried to stop timer when already running')

        self._running = False
        self._elapsed_time += (time.perf_counter() - self._start_time)

    def reset(self):
        if self._running is True:
            raise TimingException('Tried to reset timer when running')

        self._elapsed_time = 0.0

    @property
    def elapsed(self):
        if self._running is True:
            return self._elapsed_time + (time.perf_counter() - self._start_time)
        else:
            return self._elapsed_time


class TimeSimulator:
    """
    simulate a timer from a specified start date
    """

    def __init__(self):
        self._start_date = datetime.now()
        self._timer = Timer()

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
        return self._timer.elapsed

    def current(self):
        return self._start_date + timedelta(seconds=self._timer.elapsed)
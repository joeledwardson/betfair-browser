"""
time & date processes and conversion when dealing with betfair data
"""

from datetime import datetime
from myutils import timing
import logging

active_logger = logging.getLogger(__name__)


def event_time(dt: datetime, localise=True) -> str:
    """
    Time of event in HH:MM, converted from betfair UTC to local
    """
    if localise:
        dt = timing.localise(dt)
    return dt.strftime("%H:%M")


def bf_dt(dt: datetime) -> str:
    """Datetime format to use with betfair API"""
    return dt.strftime("%Y-%m-%dT%TZ")

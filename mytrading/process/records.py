"""
functions related to slicing a list of betfair records based on a criteria
"""
from betfairlightweight.resources.bettingresources import PriceSize, RunnerBook, MarketBook
from typing import List, Dict, Optional, Union
from datetime import datetime


def within_x_seconds(x, record, start_time: datetime, time_attr='publish_time'):
    """Check if a record is within x minutes of start time"""
    return 0 <= (start_time - getattr(record, time_attr)).total_seconds() <= x


def pre_off(record_list, start_time: datetime) -> List[List[MarketBook]]:
    """Get historical records before the market start time"""
    return [r for r in record_list if r[0].publish_time < start_time]


def get_recent_records(record_list, span_m, start_time: datetime) -> List[List[MarketBook]]:
    """Get records that are within 'span_m' minutes of market starttime"""
    return [r for r in record_list if within_x_seconds(span_m * 60, r[0], start_time)]


def get_recent_records_s(record_list, span_s, start_time: datetime) -> List[List[MarketBook]]:
    """Get records that are within 'span_s' seconds of market starttime"""
    return [r for r in record_list if within_x_seconds(span_s, r[0], start_time)]


def pre_inplay(record_list) -> List[List[MarketBook]]:
    """Get records before match goes in play"""
    return [r for r in record_list if not r[0].market_definition.in_play]


def record_datetimes(records) -> List[datetime]:
    """Get a list of 'publish_time' timestamps from historical records"""
    return [r[0].publish_time for r in records]
from datetime import datetime, timedelta
from typing import Optional
from myutils import registrar, datetime as utils_datetime


def format_datetime(value: datetime, dt_format: str):
    return value.strftime(dt_format)


def format_timedelta(value: timedelta, td_format: str):
    return utils_datetime.format_timedelta(td=value, fmt=td_format)


def format_money(value: Optional[float], money_format: str):
    if value is not None:
        return money_format.format(value=value)
    else:
        return None

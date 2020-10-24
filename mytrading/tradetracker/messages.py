from enum import Enum
from typing import Dict, Callable

message_formatters: Dict[Enum, Callable] = {}


def register_formatter(key: Enum):
    def decorator(func):
        message_formatters[key] = func
        return func
    return decorator


class TrackerMessages(Enum):
    TRACK_TRADE = 0
    TRACK_ORDER = 1
    MATCHED_SIZE = 2
    STATUS_UPDATE = 3


@register_formatter(TrackerMessages.TRACK_TRADE)
def formatter(attrs: Dict):
    return f'started tracking trade "{attrs.get("trade_id")}"'


@register_formatter(TrackerMessages.TRACK_ORDER)
def formatter(attrs: Dict):
    return f'started tracking order "{attrs.get("order_id")}"'


@register_formatter(TrackerMessages.MATCHED_SIZE)
def formatter(attrs: Dict):
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size")
    matched = attrs.get("size_matched")

    return f'order side {side} at {price} for £{size:.2f} now matched £{matched:.2f}'


@register_formatter(TrackerMessages.STATUS_UPDATE)
def formatter(attrs: Dict):
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size")
    status = attrs.get("status")

    return f'order side {side} at {price} for £{size:.2f}, now status {status}'


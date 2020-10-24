from enum import IntEnum
from typing import Dict, Callable
from myutils.counter import Counter

message_formatters: Dict[IntEnum, Callable] = {}
counter = Counter()


def format_message(msg_type, msg_attrs: Dict) -> str:
    """
    convert a message type and attributes into a string message
    where a formatter is not found, the message type and attributes dictionary will be returned
    """
    if msg_type in message_formatters:
        return message_formatters[msg_type](msg_attrs)
    else:
        return f'message type "{msg_type}", attributes: "{msg_attrs}"'


def next_enum() -> int:
    """get next available integer enumeration for message type keys"""
    return max(enm.value for enm in message_formatters.keys()) + 1


def register_formatter(key: IntEnum):
    """register a formatter(attrs: Dict)->str function with an integer Enumeration key to the dictionary of
    formatters"""
    def decorator(func):
        message_formatters[key] = func
        return func
    return decorator


class MessageTypes(IntEnum):
    """Enumeration types for messages"""
    TRACK_TRADE = counter.inc()
    TRACK_ORDER = counter.inc()
    MATCHED_SIZE = counter.inc()
    STATUS_UPDATE = counter.inc()
    OPEN_PLACE = counter.inc()
    MARKET_CLOSE = counter.inc()
    HEDGE_NOT_MET = counter.inc()
    BOOKS_EMPTY = counter.inc()
    GREEN_INVALID = counter.inc()
    GREEN_PLACE = counter.inc()
    HEDGE_ERROR = counter.inc()
    HEDGE_REPLACE = counter.inc()
    HEDGE_UNKNOWN = counter.inc()
    TRADE_COMPLETE = counter.inc()


@register_formatter(MessageTypes.TRACK_TRADE)
def formatter(attrs: Dict) -> str:
    return f'started tracking trade "{attrs.get("trade_id")}"'


@register_formatter(MessageTypes.TRACK_ORDER)
def formatter(attrs: Dict) -> str:
    return f'started tracking order "{attrs.get("order_id")}"'


@register_formatter(MessageTypes.MATCHED_SIZE)
def formatter(attrs: Dict) -> str:
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size", -1)
    matched = attrs.get("size_matched", -1)
    return f'order side {side} at {price} for £{size:.2f} now matched £{matched:.2f}'


@register_formatter(MessageTypes.STATUS_UPDATE)
def formatter(attrs: Dict) -> str:
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size", -1)
    status = attrs.get("status")
    return f'order side {side} at {price} for £{size:.2f}, now status {status}'


@register_formatter(MessageTypes.OPEN_PLACE)
def formatter(attrs: Dict) -> str:
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size", -1)
    return f'placing open order at {price} for £{size:.2f} on {side} side'


@register_formatter(MessageTypes.MARKET_CLOSE)
def formatter(attrs: Dict) -> str:
    return f'market closed, runner status "{attrs.get("runner_status")}"'


@register_formatter(MessageTypes.HEDGE_NOT_MET)
def formatter(attrs: Dict) -> str:
    outstanding_profit = attrs.get("outstanding_profit", -1)
    min_hedge = attrs.get("min_hedge", -1)
    return f'win/loss diff £{outstanding_profit:.2f} doesnt exceed required hedge amount £{min_hedge:.2f}'


@register_formatter(MessageTypes.BOOKS_EMPTY)
def formatter(attrs: Dict) -> str:
    return 'one side of book is completely empty...'


@register_formatter(MessageTypes.GREEN_INVALID)
def formatter(attrs: Dict) -> str:
    return f'invalid green price {attrs.get("green_price")}'


@register_formatter(MessageTypes.GREEN_PLACE)
def formatter(attrs: Dict) -> str:
    close_side = attrs.get('close_side')
    green_price = attrs.get('green_price')
    green_size = attrs.get('green_size', -1)
    return f'greening active order side {close_side} on {green_price} for £{green_size:.2f}'


@register_formatter(MessageTypes.HEDGE_ERROR)
def formatter(attrs: Dict) -> str:
    return f'error trying to hedge: "{attrs.get("order_status")}"'


@register_formatter(MessageTypes.HEDGE_REPLACE)
def formatter(attrs: Dict) -> str:
    return f'cancelling hedge at price {attrs.get("old_price")} for new price {attrs.get("new_price")}'


@register_formatter(MessageTypes.HEDGE_UNKNOWN)
def formatter(attrs: Dict) -> str:
    return f'unexpected hedge order state reached {attrs.get("order_status")}'


@register_formatter(MessageTypes.TRADE_COMPLETE)
def formatter(attrs: Dict) -> str:
    win_profit = attrs.get("win_profit", -1)
    loss_profit = attrs.get("loss_profit", -1)
    return f'trade complete, case win: £{win_profit:.2f}, case loss: £{loss_profit:.2f}'

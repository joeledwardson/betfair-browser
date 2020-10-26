from enum import Enum
from typing import Dict, Callable
from myutils.counter import Counter
import logging

active_logger = logging.getLogger(__name__)
message_formatters: Dict[Enum, Callable] = {}


def format_message(msg_type: str, msg_attrs: Dict) -> str:
    """
    convert a message type and attributes into a string message
    where a formatter is not found, the message type and attributes dictionary will be returned
    """
    if msg_type in message_formatters:
        return message_formatters[msg_type](msg_attrs)
    else:
        return f'message type "{msg_type}", attributes: "{msg_attrs}"'


def register_formatter(key: Enum):
    """
    register a formatter(attrs: Dict)->str function with an integer Enumeration key to the dictionary of
    formatters
    """
    def decorator(func):
        if key.value in message_formatters:
            raise Exception(f'registering message type {key.value}, but already exists!')
        else:
            message_formatters[key.value] = func
        return func
    return decorator


class MessageTypes(Enum):
    """Enumeration types for messages"""
    TRACK_TRADE = 'tracking new trade'
    TRACK_ORDER = 'tracking new order'
    MATCHED_SIZE = 'order matched amount change'
    STATUS_UPDATE = 'order status update'
    OPEN_PLACE = 'placing opening order'
    OPEN_ERROR = 'error status open order'
    MARKET_CLOSE = 'market closed'
    HEDGE_NOT_MET = 'hedge minimum not met'
    BOOKS_EMPTY = 'back/lay books are empty'
    GREEN_INVALID = 'invalid green price'
    GREEN_PLACE = 'placing greening order'
    HEDGE_ERROR = 'error trying to hedge'
    HEDGE_REPLACE = 'replacing hedge order'
    HEDGE_UNKNOWN = 'unknown hedge order status'
    TRADE_COMPLETE = 'trade complete'
    STATE_CHANGE = 'state change'


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
    str = f'order side {side} at {price} for £{size:.2f}, now status {status}'
    msg = attrs.get("msg")
    if msg:
        str += f', message: "{msg}"'
    return str


@register_formatter(MessageTypes.OPEN_PLACE)
def formatter(attrs: Dict) -> str:
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size", -1)
    return f'placing open order at {price} for £{size:.2f} on {side} side'


@register_formatter(MessageTypes.MARKET_CLOSE)
def formatter(attrs: Dict) -> str:
    return f'market closed, order "{attrs.get("order_id")}" runner status "{attrs.get("runner_status")}"'


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


@register_formatter(MessageTypes.OPEN_ERROR)
def formatter(attrs: Dict) -> str:
    return f'open order status is erroneous: "{attrs.get("order_status")}"'


@register_formatter(MessageTypes.STATE_CHANGE)
def formatter(attrs: Dict) -> str:
    return f'state machine changed from state "{attrs.get("old_state")}" to "{attrs.get("new_state")}"'
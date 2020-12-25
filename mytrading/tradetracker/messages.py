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
        msg = f'message type "{msg_type}"'
        for k, v in msg_attrs.items():
            msg = f'{msg}\n-> "{k}": {v}'
        return msg


def register_formatter(key: Enum):
    """
    register a formatter(attrs: Dict)->str function with an integer Enumeration key to the dictionary of
    formatters
    """
    def decorator(func):
        if key.name in message_formatters:
            raise Exception(f'registering message type "{key.name}", but already exists!')
        else:
            message_formatters[key.name] = func
        return func
    return decorator


class MessageTypes(Enum):
    """Enumeration types for messages"""
    MSG_TRACK_TRADE = 'tracking new trade'
    MSG_TRACK_ORDER = 'tracking new order'
    MSG_MATCHED_SIZE = 'order matched amount change'
    MSG_STATUS_UPDATE = 'order status update'
    MSG_OPEN_PLACE = 'placing opening order'
    MSG_OPEN_ERROR = 'error status open order'
    MSG_MARKET_CLOSE = 'market closed'
    MSG_HEDGE_NOT_MET = 'hedge minimum not met'
    MSG_BOOKS_EMPTY = 'back/lay books are empty'
    MSG_GREEN_INVALID = 'invalid green price'
    MSG_GREEN_PLACE = 'placing greening order'
    MSG_HEDGE_ERROR = 'error trying to hedge'
    MSG_HEDGE_REPLACE = 'replacing hedge order'
    MSG_HEDGE_UNKNOWN = 'unknown hedge order status'
    MSG_TRADE_COMPLETE = 'trade complete'
    MSG_STATE_CHANGE = 'state change'
    MSG_ALLOW_REACHED = 'reached allowed trading point'
    MSG_CUTOFF_REACHED = 'reached cutoff point for trading'
    MSG_LAY_EMPTY = 'lay empty'
    MSG_BACK_EMPTY = 'back empty'
    MSG_PRICE_INVALID = 'price invalid'


@register_formatter(MessageTypes.MSG_LAY_EMPTY)
def formatter(attrs: Dict) -> str:
    return f'could not place trade, lay ladder empty'


@register_formatter(MessageTypes.MSG_BACK_EMPTY)
def formatter(attrs: Dict) -> str:
    return f'could not place trade, back ladder empty'


@register_formatter(MessageTypes.MSG_TRACK_TRADE)
def formatter(attrs: Dict) -> str:
    return f'started tracking trade "{attrs.get("trade_id")}"'


@register_formatter(MessageTypes.MSG_TRACK_ORDER)
def formatter(attrs: Dict) -> str:
    return f'started tracking order "{attrs.get("order_id")}"'


@register_formatter(MessageTypes.MSG_MATCHED_SIZE)
def formatter(attrs: Dict) -> str:
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size", -1)
    matched = attrs.get("size_matched", -1)
    return f'order side {side} at {price} for £{size:.2f} now matched £{matched:.2f}'


@register_formatter(MessageTypes.MSG_STATUS_UPDATE)
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


@register_formatter(MessageTypes.MSG_OPEN_PLACE)
def formatter(attrs: Dict) -> str:
    side = attrs.get("side")
    price = attrs.get("price")
    size = attrs.get("size", -1)
    return f'placing open order at {price} for £{size:.2f} on {side} side'


@register_formatter(MessageTypes.MSG_MARKET_CLOSE)
def formatter(attrs: Dict) -> str:
    return f'market closed, order "{attrs.get("order_id")}" runner status "{attrs.get("runner_status")}"'


@register_formatter(MessageTypes.MSG_HEDGE_NOT_MET)
def formatter(attrs: Dict) -> str:
    outstanding_profit = attrs.get("outstanding_profit", -1)
    min_hedge = attrs.get("min_hedge", -1)
    return f'win/loss diff £{outstanding_profit:.2f} doesnt exceed required hedge amount £{min_hedge:.2f}'


@register_formatter(MessageTypes.MSG_BOOKS_EMPTY)
def formatter(attrs: Dict) -> str:
    return 'one side of book is completely empty...'


@register_formatter(MessageTypes.MSG_GREEN_INVALID)
def formatter(attrs: Dict) -> str:
    return f'invalid green price {attrs.get("green_price")}'


@register_formatter(MessageTypes.MSG_GREEN_PLACE)
def formatter(attrs: Dict) -> str:
    close_side = attrs.get('close_side')
    green_price = attrs.get('green_price')
    green_size = attrs.get('green_size', -1)
    order_id = attrs.get('order_id')
    return f'greening active order ID {order_id} side {close_side} on {green_price} for £{green_size:.2f}'


@register_formatter(MessageTypes.MSG_HEDGE_ERROR)
def formatter(attrs: Dict) -> str:
    return f'error trying to hedge: "{attrs.get("order_status")}"'


@register_formatter(MessageTypes.MSG_HEDGE_REPLACE)
def formatter(attrs: Dict) -> str:
    return f'cancelling hedge at price {attrs.get("old_price")} for new price {attrs.get("new_price")}'


@register_formatter(MessageTypes.MSG_HEDGE_UNKNOWN)
def formatter(attrs: Dict) -> str:
    return f'unexpected hedge order state reached {attrs.get("order_status")}'


@register_formatter(MessageTypes.MSG_TRADE_COMPLETE)
def formatter(attrs: Dict) -> str:
    win_profit = attrs.get("win_profit", -1)
    loss_profit = attrs.get("loss_profit", -1)
    return f'trade complete, case win: £{win_profit:.2f}, case loss: £{loss_profit:.2f}'


@register_formatter(MessageTypes.MSG_OPEN_ERROR)
def formatter(attrs: Dict) -> str:
    return f'open order status is erroneous: "{attrs.get("order_status")}"'


@register_formatter(MessageTypes.MSG_STATE_CHANGE)
def formatter(attrs: Dict) -> str:
    return f'state machine changed from state "{attrs.get("old_state")}" to "{attrs.get("new_state")}"'


@register_formatter(MessageTypes.MSG_CUTOFF_REACHED)
def formatter(attrs: Dict) -> str:
    cutoff_seconds = attrs.get('cutoff_seconds')
    start_time = attrs.get('start_time')
    return f'cutoff point reached {cutoff_seconds}s beofre start time: {start_time}'


@register_formatter(MessageTypes.MSG_ALLOW_REACHED)
def formatter(attrs: Dict) -> str:
    pre_seconds = attrs.get('pre_seconds')
    start_time = attrs.get('start_time')
    return f'allowed trading point reached {pre_seconds}s before start time: {start_time}'


@register_formatter(MessageTypes.MSG_PRICE_INVALID)
def formatter(attrs: Dict) -> str:
    return f'price is not a valid tick: "{attrs.get("price")}"'
from dataclasses import dataclass, field
from typing import Dict, AnyStr

from flumine.order.order import OrderStatus
from flumine.order.trade import TradeStatus


@dataclass
class OrderTracker:
    """track the status and matched money of an order"""
    matched: float
    status: OrderStatus


@dataclass
class TradeFollower:
    """track the status of a trade"""
    status: TradeStatus = field(default=None)
    order_trackers: Dict[str, OrderTracker] = field(default_factory=dict)

from dataclasses import dataclass

from flumine.order.order import OrderStatus


@dataclass
class OrderTracker:
    """track the status and matched money of an order"""
    matched: float
    status: OrderStatus
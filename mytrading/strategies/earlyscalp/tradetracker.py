from ...tradetracker.tradetracker import TradeTracker
from flumine.order.order import OrderStatus, BetfairOrder
from dataclasses import dataclass, field


class EScalpTradeTracker(TradeTracker):
    # back and lay orders
    back_order: BetfairOrder = field(default=None)
    lay_order: BetfairOrder = field(default=None)

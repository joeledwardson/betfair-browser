from mytrading.strategy.tradetracker.tradetracker import TradeTracker
from flumine.order.order import BetfairOrder
from dataclasses import field


class EScalpTradeTracker(TradeTracker):
    # back and lay orders
    back_order: BetfairOrder = field(default=None)
    lay_order: BetfairOrder = field(default=None)

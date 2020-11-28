from ...tradetracker.tradetracker import TradeTracker
from flumine.order.order import OrderStatus, BetfairOrder


class SpikeTradeTracker(TradeTracker):

    # price of back order
    back_price: float

    # price of lay order
    lay_price: float

    # back and lay orders
    back_order: BetfairOrder
    lay_order: BetfairOrder

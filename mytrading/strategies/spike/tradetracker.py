from ...tradetracker.tradetracker import TradeTracker
from flumine.order.order import OrderStatus, BetfairOrder


class SpikeTradeTracker(TradeTracker):

    # price of back order
    back_price: float

    # tick index of back order price
    back_tick_index: int

    # price of lay order
    lay_price: float

    # tick index of lay order price
    lay_tick_index: int

    # back and lay orders
    back_order: BetfairOrder
    lay_order: BetfairOrder

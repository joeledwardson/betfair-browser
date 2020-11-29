from ...tradetracker.tradetracker import TradeTracker
from flumine.order.order import OrderStatus, BetfairOrder


class SpikeTradeTracker(TradeTracker):

    # back and lay orders
    back_order: BetfairOrder
    lay_order: BetfairOrder

    # side of book which spike order has money matched
    side_matched: str

    # ltp at point of spike
    spike_ltp: float


from ...strategy.tradetracker.tradetracker import TradeTracker
from flumine.order.order import BetfairOrder
from dataclasses import field


class SpikeTradeTracker(TradeTracker):

    # back and lay orders
    back_order: BetfairOrder = field(default=None)
    lay_order: BetfairOrder = field(default=None)

    # side of book which spike order has money matched
    side_matched: str = field(default='')

    # ltp at point of spike
    spike_ltp: float = field(default=0)

    # track previous state minimum/max odds of which offset applied to place spike orders
    previous_max_index: int = field(default=0)
    previous_min_index: int = field(default=0)


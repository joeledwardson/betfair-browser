from dataclasses import dataclass, field

from ...process import BfLadderPoint
from mytrading.strategy.tradetracker.tradetracker import TradeTracker


@dataclass
class WallTradeTracker(TradeTracker):
    wall: BfLadderPoint = field(default=None)
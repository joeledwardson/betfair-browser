from dataclasses import dataclass, field

from mytrading.process.ladder import BfLadderPoint
from mytrading.tradetracker.tradetracker import TradeTracker


@dataclass
class WallTradeTracker(TradeTracker):
    wall: BfLadderPoint = field(default=None)
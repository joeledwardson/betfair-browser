from dataclasses import dataclass, field

from ...process.ladder import BfLadderPoint
from ...tradetracker.tradetracker import TradeTracker


@dataclass
class WallTradeTracker(TradeTracker):
    wall: BfLadderPoint = field(default=None)
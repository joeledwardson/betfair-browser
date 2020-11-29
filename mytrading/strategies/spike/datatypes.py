from ...tradetracker.tradetracker import TradeTracker
from dataclasses import dataclass, field


@dataclass
class SpikeData:
    best_back: float
    best_lay: float
    ltp: float
    ltp_min: float
    ltp_max: float


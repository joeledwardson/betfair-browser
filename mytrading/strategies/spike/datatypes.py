from dataclasses import dataclass


@dataclass
class SpikeData:
    best_back: float
    best_lay: float
    ladder_spread: float
    ltp: float
    ltp_min: float
    ltp_max: float


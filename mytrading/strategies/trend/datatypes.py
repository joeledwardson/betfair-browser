from dataclasses import dataclass


@dataclass
class TrendData:
    lay_gradient: float
    lay_strength: float
    back_gradient: float
    back_strength: float
    ltp_gradient: float
    ltp_strength: float

    best_back: float
    best_lay: float
    ladder_spread_ticks: int
    ltp: float

    smoothed_back: float
    smoothed_lay: float
    smoothed_ltp: float


@dataclass
class TrendCriteria:
    ladder_gradient_min: float
    ladder_strength_min: float
    ltp_gradient_min: float
    ltp_strength_min: float
    ladder_spread_max: float


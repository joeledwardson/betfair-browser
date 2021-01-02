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
    ltp: float

    ladder_spread_ticks: int

    smoothed_back: float
    smoothed_lay: float
    smoothed_ltp: float

    back_tick_movement: int
    lay_tick_movement: int
    ltp_tick_movement: int

    back_max_diff_ticks: int
    lay_max_diff_ticks: int
    ltp_max_diff_ticks: int

    @property
    def ok(self):
        return all([v is not None for v in self.__dict__.values()])


@dataclass
class TrendCriteria:
    ladder_gradient_min: float
    ladder_strength_min: float
    ladder_jump_max: int
    ltp_gradient_min: float
    ltp_strength_min: float
    ltp_jump_max: int
    ladder_spread_max: float


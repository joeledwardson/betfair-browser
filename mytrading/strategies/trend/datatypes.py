from dataclasses import dataclass, field


@dataclass
class TrendData:
    lay_gradient: float = field(default=None)
    lay_strength: float = field(default=None)
    back_gradient: float = field(default=None)
    back_strength: float = field(default=None)

    ltp_gradient: float = field(default=None)
    ltp_strength: float = field(default=None)

    best_back: float = field(default=None)
    best_lay: float = field(default=None)
    ltp: float = field(default=None)

    window_spread_ticks: int = field(default=None)
    ladder_spread_ticks: int = field(default=None)

    smoothed_back: float = field(default=None)
    smoothed_lay: float = field(default=None)
    smoothed_ltp: float = field(default=None)

    back_tick_movement: int = field(default=None)
    lay_tick_movement: int = field(default=None)
    ltp_tick_movement: int = field(default=None)

    back_max_diff_ticks: int = field(default=None)
    lay_max_diff_ticks: int = field(default=None)
    ltp_max_diff_ticks: int = field(default=None)

    @property
    def ok(self):
        return all([v is not None for v in self.__dict__.values()])


@dataclass
class TrendCriteria:
    ladder_gradient_min: float
    ladder_strength_min: float

    ltp_gradient_min: float
    ltp_strength_min: float

    ladder_jump_max: int
    ltp_jump_max: int

    ladder_spread_max: float
    window_spread_min: int

    ladder_movement_ticks: int
    ltp_movement_ticks: int


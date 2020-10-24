from typing import Dict
from enum import IntEnum
from mytrading.tradetracker.messages import register_formatter, next_enum
from myutils.counter import Counter

counter = Counter(next_enum())


class WallMessageTypes(IntEnum):
    NO_WALL = counter.inc()
    NO_WALL_PRICE = counter.inc()
    WALL_SIZE_FAIL = counter.inc()
    WALL_DETECT = counter.inc()
    WALL_VARIABLE_INVALID = counter.inc()
    REPLACE_WALL_ORDER = counter.inc()
    WALL_TAKE_HEDGE = counter.inc()


@register_formatter(WallMessageTypes.NO_WALL)
def formatter(attrs: Dict):
    return f'wall validation failed: no wall instance found in trade_tracker'


@register_formatter(WallMessageTypes.NO_WALL_PRICE)
def formatter(attrs: Dict):
    return f'wall validation failed: no price info detected at wall price {attrs.get("wall_price")}'


@register_formatter(WallMessageTypes.WALL_SIZE_FAIL)
def formatter(attrs: Dict):
    wall_price = attrs.get('wall_price')
    wall_size = attrs.get('wall_size', -1)
    wall_validation = attrs.get('wall_validation')
    old_wall_size = attrs.get('old_wall_size', -1)

    return f'wall validation failed:  current amount at wall price {wall_price} of £{wall_size:.2f} is less than ' \
           f'validation multiplier {wall_validation} of original size £{old_wall_size:.2f}'


@register_formatter(WallMessageTypes.WALL_DETECT)
def formatter(attrs: Dict):
    wall_point = attrs.get('wall_point')
    best_b = attrs.get('best_atb')
    best_l = attrs.get('best_atl')
    spread_ticks = attrs.get('spread_ticks')

    return f'detected wall {wall_point}, best back {best_b}, best lay {best_l}, spread ticks {spread_ticks}'


@register_formatter(WallMessageTypes.WALL_VARIABLE_INVALID)
def formatter(attrs: Dict):
    return f'wall variables detected is None, which is valid'


@register_formatter(WallMessageTypes.REPLACE_WALL_ORDER)
def formatter(attrs: Dict):
    f'replacing active order at price {attrs.get("price")} with new price {attrs.get("new_price")}'


@register_formatter(WallMessageTypes.WALL_TAKE_HEDGE)
def formatter(attrs: Dict):
    f'wall validation failed, binning trade then taking available'


from typing import Dict
from enum import Enum
from mytrading.tradetracker.messages import register_formatter


class WindowMessageTypes(Enum):
    TRACK_START = 'tracking breach of window'
    TRACK_SUCCESS = 'breach window successfully'
    TRACK_FAIL = 'window breach failed'
    OPEN_PLACE_FAIL = 'open order place fail'
    PLACE_DRIFT = 'ltp drifted since open place'
    DIRECTION_CHANGE = 'breach opposite window'


def get_window_name(direction_up: bool) -> str:
    if bool(direction_up):
        return 'LTP max'
    else:
        return 'LTP min'


def get_direction(direction_up: bool) -> str:
    return 'up' if direction_up else 'down'


@register_formatter(WindowMessageTypes.TRACK_START)
def formatter(attrs: Dict) -> str:
    window_name = get_window_name(attrs.get('direction_up'))
    ltp = attrs.get('ltp')
    ltp_max = attrs.get('ltp_max')
    window_value = attrs.get('window_value')
    window_spread = attrs.get('window_spread')
    ltp_min_spread = attrs.get('window_spread_min')
    ladder_spread = attrs.get('ladder_spread')
    ladder_spread_max = attrs.get('ladder_spread_max')

    return \
        f'tracking window breach of {window_name} at {window_value:.2f} with LTP of {ltp}\n' \
        f'-> ltp {ltp} within max odds {ltp_max}\n' \
        f'-> window spread {window_spread} exceeds minimum {ltp_min_spread}\n' \
        f'-> and ladder spread {ladder_spread} within max {ladder_spread_max}'


@register_formatter(WindowMessageTypes.TRACK_SUCCESS)
def formatter(attrs: Dict) -> str:
    window_name = get_window_name(attrs.get('direction_up'))
    return f'successfully window breach of {window_name}, '


@register_formatter(WindowMessageTypes.TRACK_FAIL)
def formatter(attrs: Dict) -> str:
    window_name = get_window_name(attrs.get('direction_up'))
    ltp = attrs.get('ltp')
    ltp_max = attrs.get('ltp_max')
    window_value = attrs.get('window_value')
    window_spread = attrs.get('window_spread')
    ltp_min_spread = attrs.get('window_spread_min')
    ladder_spread = attrs.get('ladder_spread')
    ladder_spread_max = attrs.get('ladder_spread_max')

    return \
        f'breach of {window_name} at {window_value:.2f} failed, with LTP of {ltp}\n' \
        f'-> ltp {ltp} must be within {ltp_max}\n' \
        f'-> window spread {window_spread} must exceed minimum {ltp_min_spread}\n' \
        f'-> and ladder spread {ladder_spread} must be within {ladder_spread_max}'


@register_formatter(WindowMessageTypes.OPEN_PLACE_FAIL)
def formatter(attrs: Dict) -> str:
    return f'failed to place open oder: {attrs.get("reason")}'


@register_formatter(WindowMessageTypes.PLACE_DRIFT)
def formatter(attrs: Dict) -> str:
    direction = get_direction(attrs.get('direction_up'))
    return f'ltp drifted {direction} from {attrs.get("old_ltp")} to {attrs.get("ltp")}'


@register_formatter(WindowMessageTypes.DIRECTION_CHANGE)
def formatter(attrs: Dict) -> str:
    direction = get_direction(attrs.get('direction_up'))
    ltp = attrs.get("ltp")
    window_value = attrs.get('window_value')
    window_name = get_window_name(attrs.get('direction_up'))
    return f'tracking {direction} direction has reversed, LTP {ltp} breached {window_name} at {window_value:.2f}'
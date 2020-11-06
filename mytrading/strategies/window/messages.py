from typing import Dict
from enum import Enum
from ...tradetracker.messages import register_formatter


class WindowMessageTypes(Enum):
    WDW_MSG_TRACK_START = 'tracking breach of window'
    WDW_MSG_TRACK_SUCCESS = 'breach window successfully'
    WDW_MSG_TRACK_FAIL = 'window breach failed'
    WDW_MSG_PLACE_DRIFT = 'ltp drifted since open place'
    WDW_MSG_DIR_CHANGE = 'breach opposite window'
    WDW_MSG_LTP_FAIL = 'ltp not breached bounds'
    WDW_MSG_LAY_INVALID = 'lay invalid'
    WDW_MSG_BACK_INVALID = 'back invalid'
    WDW_MSG_STK_INVALID = 'stake size invalid'


class WindowMessageFailTypes(Enum):
    BEST_LAY_INVALID = 'best lay invalid'
    BEST_BACK_INVALID = 'best back invalid'
    STAKE_SIZE_INVALID = 'stake size invalid'
    LTP_BREACH_FAIL = 'ltp not breached bounds'


def get_window_name(direction_up: bool) -> str:
    if bool(direction_up):
        return 'LTP max'
    else:
        return 'LTP min'


def get_direction(direction_up: bool) -> str:
    return 'up' if direction_up else 'down'


def get_window_breach_info(attrs: dict) -> str:
    window_name = get_window_name(attrs.get('direction_up'))
    ltp = attrs.get('ltp')
    ltp_max = attrs.get('ltp_max')
    window_value = attrs.get('window_value')
    window_spread = attrs.get('window_spread')
    ltp_min_spread = attrs.get('window_spread_min')
    ladder_spread = attrs.get('ladder_spread')
    ladder_spread_max = attrs.get('ladder_spread_max')
    total_matched = attrs.get('total_matched', 0)
    min_total_matched = attrs.get('min_total_matched', 0)

    return \
        f'-> LTP is {ltp}, vs {window_name} of {window_value:.2f}\n' \
        f'-> total matched £{total_matched:.2f} >= minimum required £{min_total_matched:.2f}\n' \
        f'-> LTP {ltp} within max odds {ltp_max}\n' \
        f'-> window spread {window_spread} exceeds minimum {ltp_min_spread}\n' \
        f'-> and ladder spread {ladder_spread} within max {ladder_spread_max}'


@register_formatter(WindowMessageTypes.WDW_MSG_TRACK_START)
def formatter(attrs: Dict) -> str:
    window_name = get_window_name(attrs.get('direction_up'))
    breach_info = get_window_breach_info(attrs)
    return f'tracking window breach of {window_name}\n{breach_info}'


@register_formatter(WindowMessageTypes.WDW_MSG_TRACK_SUCCESS)
def formatter(attrs: Dict) -> str:
    window_name = get_window_name(attrs.get('direction_up'))
    breach_info = get_window_breach_info(attrs)
    return f'successful window breach of {window_name}\n{breach_info}'


@register_formatter(WindowMessageTypes.WDW_MSG_TRACK_FAIL)
def formatter(attrs: Dict) -> str:
    window_name = get_window_name(attrs.get('direction_up'))
    breach_info = get_window_breach_info(attrs)
    return f'breach of {window_name} failed\n{breach_info}'


@register_formatter(WindowMessageTypes.WDW_MSG_PLACE_DRIFT)
def formatter(attrs: Dict) -> str:
    direction = get_direction(attrs.get('direction_up'))
    return f'ltp drifted {direction} from {attrs.get("old_ltp")} to {attrs.get("ltp")}'


@register_formatter(WindowMessageTypes.WDW_MSG_DIR_CHANGE)
def formatter(attrs: Dict) -> str:
    direction = get_direction(attrs.get('direction_up'))
    ltp = attrs.get("ltp")
    window_value = attrs.get('window_value')
    window_name = get_window_name(attrs.get('direction_up'))
    return f'tracking {direction} direction has reversed, LTP {ltp} breached {window_name} at {window_value:.2f}'


@register_formatter(WindowMessageTypes.WDW_MSG_LTP_FAIL)
def formatter(attrs: Dict) -> str:
    return f'fail placing trade: ltp {attrs.get("ltp")} not breached min {attrs.get("ltp_min")} or max' \
           f' {attrs.get("ltp_max")}'


@register_formatter(WindowMessageTypes.WDW_MSG_LAY_INVALID)
def formatter(attrs: Dict) -> str:
    return f'fail placing trade going up, best lay is 0'


@register_formatter(WindowMessageTypes.WDW_MSG_BACK_INVALID)
def formatter(attrs: Dict) -> str:
    return f'fail placing trade going down, best back is 0'


@register_formatter(WindowMessageTypes.WDW_MSG_STK_INVALID)
def formatter(attrs: Dict) -> str:
    start_stake_size = attrs.get('start_stake_size', 0)
    matched = attrs.get('matched', 0)
    stake_size = attrs.get('stake_size', 0)
    return f'stake size £{stake_size:.2f} is invalid, original size £{start_stake_size:.2f} & matched £{matched:.2f}'

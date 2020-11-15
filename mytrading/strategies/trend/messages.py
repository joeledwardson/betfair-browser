from typing import Dict
from enum import Enum
from ...tradetracker.messages import register_formatter
from .datatypes import TrendData, TrendCriteria

# regression gradient % decimal places to display
GR_DP = 2

# regression strength (r-squared) % decimal places to display
S_DP = 0


class TrendMessageTypes(Enum):
    TREND_MSG_START = 'achieved trend criteria'
    TREND_MSG_REVERSE = 'trend reversed'
    TREND_MSG_PRICE_SPIKE = 'price spiked'
    TREND_MSG_PRICE_MOVE = 'price moved'


@register_formatter(TrendMessageTypes.TREND_MSG_START)
def formatter(attrs: Dict) -> str:

    trend_data_kwargs = attrs.get('trend_data', {})
    trend_criteria_kwargs = attrs.get('trend_criteria', {})
    direction = 'up' if attrs.get('direction_up') else 'down'

    try:
        data = TrendData(**trend_data_kwargs)
        criteria = TrendCriteria(**trend_criteria_kwargs)

        return '\n'.join([
            f'back/lay/ltp met regression criteria going {direction}',
            f'-> lay gradient {data.lay_gradient:.{GR_DP}%} meets requirement >= '
            f'{criteria.ladder_gradient_min:.{GR_DP}%}',
            f'-> lay strength {data.lay_strength:.{S_DP}%} meets requirement >= '
            f'{criteria.ladder_strength_min:.{S_DP}%}',
            f'-> back gradient {data.back_gradient:.{GR_DP}%} meets requirement >= '
            f'{criteria.ladder_gradient_min:.{GR_DP}%}',
            f'-> back strength {data.back_strength:.{S_DP}%} meets requirement >= '
            f'{criteria.ladder_strength_min:.{S_DP}%}',
            f'-> ltp gradient {data.ltp_gradient:.{GR_DP}%} meets requirement >= '
            f'{criteria.ltp_gradient_min:.{GR_DP}%}',
            f'-> back strength {data.ltp_strength:.{S_DP}%} meets requirement >= '
            f'{criteria.ladder_strength_min:.{S_DP}%}',
            f'-> spread between smoothed back {data.smoothed_back:.2f} & smoothed lay {data.smoothed_lay:.2f} is '
            f'{data.ladder_spread_ticks} ticks, meets requirement <= {criteria.ladder_spread_max}'
        ])

    except Exception:
        return f'sucessful trend: could not process trend/criteria for "TREND_MSG_START" message, attrs passed: ' \
               f'{list(attrs.keys())}'



@register_formatter(TrendMessageTypes.TREND_MSG_REVERSE)
def formatter(attrs: Dict) -> str:

    trend_data_kwargs = attrs.get('trend_data', {})
    direction = 'up' if attrs.get('direction_up') else 'down'

    try:
        data = TrendData(**trend_data_kwargs)

        return '\n'.join([
            f'direction {direction} has reversed',
            f'-> lay gradient now {data.lay_gradient:.{GR_DP}%}'
            f'-> back gradient now {data.back_gradient:.{GR_DP}%}'
        ])

    except Exception:
        return f'trend reverse: could not process trend data from kwargs {trend_data_kwargs}'


@register_formatter(TrendMessageTypes.TREND_MSG_PRICE_SPIKE)
def formatter(attrs: Dict) -> str:
    direction_up = attrs.get('direction_up')
    order_price = attrs.get('order_price', 0)
    new_price = attrs.get('new_price', 0)

    if direction_up:
        return f'trend up, best back moved from order price {order_price:.2f} to {new_price:.2f}'
    else:
        return f'trend down, best lay moved from order price {order_price:.2f} to {new_price:.2f}'


@register_formatter(TrendMessageTypes.TREND_MSG_PRICE_MOVE)
def formatter(attrs: Dict) -> str:
    direction_up = attrs.get('direction_up')
    order_price = attrs.get('order_price', 0)
    hold_ms = attrs.get('hold_ms')

    if direction_up:
        return f'trend up, best back moved from order price {order_price:.2f} and held for {hold_ms} ms'
    else:
        return f'trend down, best lay moved from order price {order_price:.2f} and held for {hold_ms} ms'


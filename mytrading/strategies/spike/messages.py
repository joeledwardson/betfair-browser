from typing import Dict
from enum import Enum
from ...tradetracker.messages import register_formatter


class SpikeMessageTypes(Enum):
    SPIKE_MSG_START = 'achieved spike criteria'
    SPIKE_MSG_ENTER_FAIL = 'failed on enter window state'
    SPIKE_MSG_CREATE = 'place opening window trades'
    SPIKE_MSG_PRICE_REPLACE = 'replacing price'


@register_formatter(SpikeMessageTypes.SPIKE_MSG_START)
def formatter(attrs: Dict) -> str:

    return '\n'.join([
        f'criteria met:',
        f'-> best back: {attrs.get("best_back", 0):.2f}, best lay: {attrs.get("best_lay", 0):.2f}',
        f'-> ladder spread: {attrs.get("ladder_spread", 0)} within max: {attrs.get("ladder_spread_max", 0)}',
        f'-> ltp min: {attrs.get("ltp_min", 0):.2f}, ltp max: {attrs.get("ltp_max", 0):.2f}',
        f'-> window spread: {attrs.get("window_spread", 0)} meets minimum: {attrs.get("window_spread_min", 0)}'
    ])


@register_formatter(SpikeMessageTypes.SPIKE_MSG_CREATE)
def formatter(attrs: Dict) -> str:

    return f'placing opening "{attrs.get("side")}" order at {attrs.get("price", 0):.2f} for ' \
           f'£{attrs.get("size", 0):.2f}'


@register_formatter(SpikeMessageTypes.SPIKE_MSG_ENTER_FAIL)
def formatter(attrs: Dict) -> str:

    return '\n'.join([
        f'variable in attributes not non-zero:',
        f'-> best back: {attrs.get("best_back")}',
        f'-> best lay: {attrs.get("best_lay")}',
        f'-> ltp: {attrs.get("ltp")}',
        f'-> ltp min: {attrs.get("ltp_min")}',
        f'-> ltp max: {attrs.get("ltp_max")}'
    ])


@register_formatter(SpikeMessageTypes.SPIKE_MSG_PRICE_REPLACE)
def formatter(attrs: Dict) -> str:

    return f'replacing order on "{attrs.get("side")}" side from {attrs.get("old_price", 0):.2f} to new price '\
    f'{attrs.get("new_price", 0):.2f}'


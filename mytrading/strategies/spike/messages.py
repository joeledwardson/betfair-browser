from typing import Dict
from enum import Enum
from ...strategy.tradetracker.messages import register_formatter


class SpikeMessageTypes(Enum):
    SPIKE_MSG_START = 'achieved spike criteria'
    SPIKE_MSG_VAL_FAIL = 'failed to validate spike data'
    SPIKE_MSG_CREATE = 'place opening window trades'
    SPIKE_MSG_PRICE_REPLACE = 'replacing price'
    SPIKE_MSG_BREACHED = 'spike reached'
    SPIKE_MSG_SPREAD_FAIL = 'spread validation fail'


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


@register_formatter(SpikeMessageTypes.SPIKE_MSG_VAL_FAIL)
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


@register_formatter(SpikeMessageTypes.SPIKE_MSG_BREACHED)
def formatter(attrs: Dict) -> str:

    return f'spike detected on "{attrs.get("side")}" from boundary {attrs.get("old_price", 0):.2f} to ltp ' \
           f'{attrs.get("ltp", 0):.2f} by {attrs.get("spike_ticks")} ticks'


@register_formatter(SpikeMessageTypes.SPIKE_MSG_SPREAD_FAIL)
def formatter(attrs: Dict) -> str:

    return f'failed to validate ladder spread or window spread' \
           f'ladder spread: {attrs.get("ladder_spread")} must be <= max: {attrs.get("ladder_spread_max")}\n' \
           f'window spread: {attrs.get("window_spread")} must be >= min: {attrs.get("window_spread_min")}'


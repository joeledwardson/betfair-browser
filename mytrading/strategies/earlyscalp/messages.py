from typing import Dict
from enum import Enum
from mytrading.strategy.tradetracker.messages import register_formatter


class EScalpMessageTypes(Enum):
    ESCALP_MSG_START = 'achieved scalp criteria'
    ESCALP_MSG_STOP = 'reached cutoff point for starting new trades'
    ESCALP_SPREAD_FAIL = 'spread validation failed'


@register_formatter(EScalpMessageTypes.ESCALP_MSG_START)
def formatter(attrs: Dict) -> str:

    return '\n'.join([
        f'criteria met:',
        f'-> average spread {attrs.get("spread"):.2f} is >= minimum required {attrs.get("spread_min")}'
    ])


@register_formatter(EScalpMessageTypes.ESCALP_MSG_STOP)
def formatter(attrs: Dict) -> str:
    return f'reached cutoff point for starting new trades {attrs.get("cutoff_s")}s before start'


@register_formatter(EScalpMessageTypes.ESCALP_SPREAD_FAIL)
def formatter(attrs: Dict) -> str:
    return f'average spread {attrs.get("spread"):.2f} does not meet criteria {attrs.get("spread_min")}'


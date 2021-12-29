from __future__ import annotations
from typing import List
import dash


def triggered_id() -> str:
    """assume single component triggered callback, return its ID, or blank string if no trigger elemt"""
    ctx = dash.callback_context
    if not ctx.triggered:
        return ''
    else:
        return ctx.triggered[0]['prop_id'].split('.')[0]


def all_triggered_ids() -> List[str]:
    """return list of components IDs that have triggered callback"""
    ctx = dash.callback_context
    return[t['prop_id'].split('.')[0] for t in ctx.triggered if t]



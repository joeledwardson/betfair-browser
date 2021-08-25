from __future__ import annotations
import dash
import dash_html_components as html
from typing import List, Dict


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


def hidden_div(div_id) -> html.Div:
    return html.Div(
        children='',
        style={'display': 'none'},
        id=div_id,
    )


class Intermediary:
    """
    increment value and return string for intermediaries
    """
    def __init__(self):
        self.value = 0

    def next(self):
        self.value += 1
        return str(self.value)


class CSSClassHandler:
    def __init__(self, names: str, separator=' '):
        self._sep = separator
        self._names = names.split(self._sep)

    @staticmethod
    def from_list(names_list: List[str], separator) -> CSSClassHandler:
        obj = CSSClassHandler('', separator=separator)
        obj._names = names_list
        return obj

    def _formatter(self):
        return self._sep.join(self._names)

    def __add__(self, other: str):
        new_names = self._names.copy()
        if other not in new_names:
            new_names.append(other)
        return self.from_list(new_names, self._sep)

    def __sub__(self, other):
        new_names = self._names.copy()
        if other in new_names:
            new_names.pop(new_names.index(other))
        return self.from_list(new_names, self._sep)

    def __str__(self):
        return self._formatter()

    def __repr__(self):
        return self._formatter()
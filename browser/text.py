from typing import List
import dash_html_components as html
from itertools import chain


def html_lines(text_lines: List[str], element=html.Div):
    return [
        element(str(txt))
        for txt in chain(*(
            x.split('\n') for x in text_lines
        ))
    ]
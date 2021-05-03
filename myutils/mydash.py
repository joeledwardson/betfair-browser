import dash
import dash_html_components as html


def triggered_id() -> str:
    ctx = dash.callback_context
    if not ctx.triggered:
        return ''
    else:
        return ctx.triggered[0]['prop_id'].split('.')[0]


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
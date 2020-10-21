import dash


def triggered_id() -> str:
    ctx = dash.callback_context
    if not ctx.triggered:
        return ''
    else:
        return ctx.triggered[0]['prop_id'].split('.')[0]
import dash_html_components as html


def log_box():
    return html.Div(
        id='logger-box',
        className='d-flex flex-column-reverse overflow-auto bg-light',
        children=[],
    )

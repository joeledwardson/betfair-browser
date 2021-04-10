import dash_html_components as html


def log_box():
    # bottom logging box
    return html.Div(
        id='logger-box',
        # use display flex and reverse div row order so first in list appears at bottom, so that scroll bar
        # stays at bottom (log messages must be append back to front, with new messages added to start of list)
        style={
            'display': 'flex',
            'flex-direction': 'column-reverse',
            'overflow-y': 'scroll',
            # 'grid-column-start': '1',
            # 'grid-column-end': '3',
            'background-color': 'lightgrey',
            'height': '60vh',
            # 'align-self': 'end',
            # 'margin': 5,
        },
        children=[],
    )

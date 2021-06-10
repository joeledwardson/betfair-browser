import dash_html_components as html


def log_config_spec(config):
    return {
        'container-id': 'container-logs',
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Python Log'
                },
            ],
            {
                'type': 'element-div',
                'id': 'logger-box',
                'css_classes': 'd-flex flex-column-reverse overflow-auto bg-light'
            }
        ]
    }


def log_box():
    return html.Div(
        id='logger-box',
        className='d-flex flex-column-reverse overflow-auto bg-light',
        children=[],
    )

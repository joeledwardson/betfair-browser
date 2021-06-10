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

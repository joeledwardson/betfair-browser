
def strategy_modal_spec():
    return {
        'type': 'element-modal',
        'id': 'strategy-delete-modal',
        'header_spec': 'Delete strategy?',
        'footer_spec': [
            {
                'type': 'element-button',
                'btn_text': 'Yes',
                'id': 'strategy-delete-yes',
                'color': 'danger'
            },
            {
                'type': 'element-button',
                'btn_text': 'No',
                'id': 'strategy-delete-no',
                'color': 'success'
            }
        ]
    }


def strategy_config_spec(config):
    full_tbl_cols = dict(config['STRATEGY_TABLE_COLS'])
    n_rows = int(config['TABLE']['strategy_rows'])
    return {
        'container-id': 'container-strategy',
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Strategies'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-strategy-filter',
                    'btn_icon': 'fas fa-filter',
                },
                {
                    'type': 'element-navigation-button',
                    'id': 'nav-strategy-download',
                    'href': '/',
                    'btn_id': 'btn-strategy-download',
                    'btn_icon': 'fas fa-download'
                }
            ],
            [
                {
                    'type': 'element-button',
                    'id': 'btn-strategy-refresh',
                    'btn_text': 'Reload',
                    'btn_icon': 'fas fa-sync-alt'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-strategy-delete',
                    'btn_text': 'Delete strategy',
                    'btn_icon': 'fas fa-trash',
                    'color': 'danger'
                }
            ],
            [
                {
                    'type': 'element-stylish-select',
                    'id': 'input-strategy-run',
                    'placeholder': 'Strategy config...',
                    'clear_id': 'strategy-run-clear',
                },
                {
                    'type': 'element-button',
                    'id': 'btn-strategies-reload',
                    'btn_text': 'Reload configs...',
                    'color': 'info',
                },
                {
                    'type': 'element-button',
                    'id': 'btn-strategy-run',
                    'btn_text': 'Run strategy',
                    'btn_icon': 'fas fa-play-circle'
                },
            ],
            {
                'type': 'element-table',
                'id': 'table-strategies',
                'columns': full_tbl_cols,
                'n_rows': n_rows
            }
        ],
    }


def strategy_sidebar_spec():
    return {
        'sidebar_id': 'container-filters-strategy',
        'sidebar_title': 'Strategy Filters',
        'close_id': 'btn-strategy-close',
        'content': [
            {
                'type': 'element-select',
                'id': 'input-strategy-select',
                'placeholder': 'Strategy...'
            }
        ]
    }
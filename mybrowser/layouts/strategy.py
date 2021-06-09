
def strategy_config_spec(config):
    full_tbl_cols = dict(config['STRATEGY_TABLE_COLS'])
    n_rows = int(config['TABLE']['strategy_rows'])
    return {
        'container-id': 'container-strategy',
        'content': [
            [
                {
                    'type': 'header',
                    'children_spec': 'Strategies'
                },
                {
                    'type': 'button',
                    'id': 'btn-strategy-filter',
                    'btn_icon': 'fas fa-filter',
                },
                {
                    'type': 'nav-link',
                    'id': 'nav-strategy-download',
                    'href': '/',
                    'btn_id': 'btn-strategy-download',
                    'btn_icon': 'fas fa-download'
                }
            ],
            [
                {
                    'type': 'button',
                    'id': 'btn-strategy-refresh',
                    'btn_text': 'Reload',
                    'btn_icon': 'fas fa-sync-alt'
                },
                {
                    'type': 'button',
                    'id': 'btn-strategy-delete',
                    'btn_text': 'Delete strategy',
                    'btn_icon': 'fas fa-trash',
                    'color': 'danger'
                }
            ],
            [
                {
                    'type': 'stylish-select',
                    'id': 'input-strategy-run',
                    'placeholder': 'Strategy config...',
                    'clear_id': 'strategy-run-clear',
                },
                {
                    'type': 'button',
                    'id': 'btn-strategies-reload',
                    'btn_text': 'Reload configs...',
                    'color': 'info',
                },
                {
                    'type': 'button',
                    'id': 'btn-strategy-run',
                    'btn_text': 'Run strategy',
                    'btn_icon': 'fas fa-play-circle'
                },
            ],
            {
                'type': 'table',
                'id': 'table-strategies',
                'columns': full_tbl_cols,
                'n_rows': n_rows
            }
        ],
        'sidebar': {
            'sidebar_id': 'container-filters-strategy',
            'sidebar_title': 'Strategy Filters',
            'close_id': 'btn-strategy-close',
            'content': [
                {
                    'type': 'select',
                    'id': 'input-strategy-select',
                    'placeholder': 'Strategy...'
                }
            ]
        }
    }

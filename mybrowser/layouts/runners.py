
def runner_loading_spec():
    return {
        'type': 'element-loading',
        'id': 'loading-out-runners',
    }


def figure_loading_spec():
    return {
        'type': 'element-loading',
        'id': 'loading-out-figure'
    }


def runners_config_spec(config):
    full_tbl_cols = dict(config['RUNNER_TABLE_COLS'])
    n_rows = int(config['TABLE']['runner_rows'])
    return {
        'container-id': 'container-runners',
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Runner Info'
                },
                {
                    'type': 'element-button',
                    'id': 'btn-runners-filter',
                    'btn_icon': 'fas fa-bars'
                },
                {
                    'type': 'element-button',
                    'id': 'button-mkt-bin',
                    'btn_icon': 'fas fa-trash',
                    'color': 'warning',
                }
            ],
            [
                {
                    'type': 'element-button',
                    'id': 'button-orders',
                    'btn_icon': 'fas fa-file-invoice-dollar',
                    'btn_text': 'Orders',
                    'color': 'info',
                },
                {
                    'type': 'element-button',
                    'id': 'button-figure',
                    'btn_icon': 'fas fa-chart-line',
                    'btn_text': 'Figure',
                },
                {
                    'type': 'element-button',
                    'id': 'button-all-figures',
                    'btn_icon': 'fas fa-chart-line',
                    'btn_text': 'All Figures',
                },
            ],
            [
                {
                    'type': 'element-div',
                    'id': 'infobox-market'
                }
            ],
            {
                'type': 'element-table',
                'id': 'table-runners',
                'columns': full_tbl_cols,
                'n_rows': n_rows
            }
        ],
    }


def runners_sidebar_spec(config):
    return {
        'sidebar_id': 'container-filters-plot',
        'sidebar_title': 'Plot Config',
        'close_id': 'btn-plot-close',
        'content': [
            {
                'type': 'element-select',
                'id': 'input-feature-config',
                'placeholder': 'Feature config...'
            },
            {
                'type': 'element-select',
                'id': 'input-plot-config',
                'placeholder': 'Plot config...',
            },
            {
                'type': 'element-button',
                'id': 'button-feature-config',
                'btn_text': 'Reload feature configs',
                'btn_icon': 'fas fa-sync-alt',
                'color': 'info'
            },
            {
                'type': 'element-input-group',
                'children_spec': [
                    {
                        'type': 'element-input-group-addon',
                        'children_spec': 'Input offset: ',
                    },
                    {
                        'type': 'element-input',
                        'id': 'input-chart-offset',
                        'element_kwargs': {
                            'type': 'time',
                            'step': '1',  # forces HTML to use hours, minutes and seconds format
                            'value': config['PLOT_CONFIG']['default_offset']
                        }
                    }
                ]
            }
        ]
    }


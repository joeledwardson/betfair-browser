def timings_config_spec(config):
    tbl_cols = dict(config['TIMINGS_TABLE_COLS'])
    n_rows = int(config['TABLE']['timings_rows'])
    return {
        'container-id': 'container-timings',
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Function Timings'
                },
            ],
            {
                'type': 'element-table',
                'id': 'table-timings',
                'columns': tbl_cols,
                'n_rows': n_rows
            }
        ]
    }


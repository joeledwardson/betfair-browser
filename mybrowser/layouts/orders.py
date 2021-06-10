def orders_config_spec(config):
    tbl_cols = dict(config['ORDER_TABLE_COLS'])
    n_rows = int(config['TABLE']['orders_rows'])
    return {
        'container-id': 'container-orders',
        'content': [
            [
                {
                    'type': 'element-header',
                    'children_spec': 'Order Profits'
                },
            ],
            {
                'type': 'element-table',
                'id': 'table-orders',
                'columns': tbl_cols,
                'n_rows': n_rows,
                'no_fixed_widths': True,
            }
        ]
    }


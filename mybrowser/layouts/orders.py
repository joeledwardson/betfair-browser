import dash_html_components as html
import dash_table


def log_config_spec(config):
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
            }
        ]
    }


def header():
    # orders header
    return html.H2(
        children='Order Profits'
    )



def table(n_rows) -> dash_table.DataTable:
    """
    get empty DataTable for order profits
    """
 
    return dash_table.DataTable(
        id='table-orders',
        columns=[{
            'name': 'Timestamp',
            'id': 'date'
        }, {
            'name': 'Trade Index',
            'id': 'trade'
        }, {
            'name': 'Side',
            'id': 'side',
        }, {
            'name': 'Price',
            'id': 'price'
        }, {
            'name': 'Size',
            'id': 'size',
        }, {
            'name': 'Matched Price',
            'id': 'm-price',
        }, {
            'name': 'Matched',
            'id': 'matched',
        }, {
            'name': 'Order',
            'id': 'order-profit'
        }, {
            'name': 'Trade',
            'id': 'trade-profit'
        }, {
            'name': 'Time to Start',
            'id': 't-start'
        }],
        style_cell={
            'textAlign': 'left',
        },
        style_table={
            'overflowX': 'scroll'
        },
        page_size=n_rows
    )

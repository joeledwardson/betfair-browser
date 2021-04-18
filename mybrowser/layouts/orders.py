import dash_html_components as html
import dash_table
from mytrading.visual import profits


def header():
    # orders header
    return html.H2(
        children='Order Profits'
    )


# TODO - tables cannot use 'fixed_headers=True' with % height parent or else chrome winges about "Maximum call stack
#  exceeded" - however it works fine with paginated tables - probably worth posting about on forum
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

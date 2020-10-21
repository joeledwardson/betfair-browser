import dash_table


def get_market_table(
        id='table-market',
        height=140,
        width=600
) -> dash_table.DataTable:
    """get empty mydash DataTable for runner information"""
    return dash_table.DataTable(
        id=id,
        columns=[{
            'name': x,
            'id': x
        } for x in ['Attribute', 'Value']],
        fixed_rows={
            'headers': True
        },
        style_table={
            'height': height,
            'width': width,
        },
        style_cell={
            'textAlign': 'left'
        },
    )
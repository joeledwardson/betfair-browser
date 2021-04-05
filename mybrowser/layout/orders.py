from typing import Optional
from datetime import timedelta
import dash_html_components as html
import dash_core_components as dcc
import dash_table
import pandas as pd
from myutils import mytiming
from typing import Dict, List
import logging
import dash_table
from mytrading.visual import profits
from myutils.mydash import intermediate
from ..tables.table import create_table
from ..tables.orders import get_orders_table


def header():
    # orders header
    return html.H2(
        children='Order Profits'
    )


# TODO - tables cannot use 'fixed_headers=True' with % height parent or else chrome winges about "Maximum call stack
#  exceeded" - however it works fine with paginated tables - probably worth posting about on forum

# TODO - make page size part of config
def table(height) -> dash_table.DataTable:
    """
    get empty DataTable for order profits
    """
    return dash_table.DataTable(
        id='table-orders',
        columns=[{
            'name': x,
            'id': x
        } for x in profits.PROFIT_COLUMNS],
        style_cell={
            'textAlign': 'left',
        },
        style_table={
            'overflowX': 'scroll'
        },
        page_size=8,
    )

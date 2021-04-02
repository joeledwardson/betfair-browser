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
from ..tables.table import create_table
from ..tables.orders import get_orders_table


def header():
    # orders header
    return html.H2(
        children='Order Profits'
    )


def table(height) -> dash_table.DataTable:
    """
    get empty DataTable for order profits
    """
    return create_table(
        table_id='table-orders',
        df=pd.DataFrame({
            x: []
            for x in profits.PROFIT_COLUMNS
        }),
        height=height,
    )

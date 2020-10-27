from typing import Dict, List
import logging
import pandas as pd
import dash_table
from ..tables.table import create_table
from ...visual.profits import PROFIT_COLUMNS

active_logger = logging.getLogger(__name__)


def get_orders_table(
        table_id='table-orders',
) -> dash_table.DataTable:
    """get empty DataTable for order profits"""
    return create_table(
        table_id=table_id,
        df=pd.DataFrame({
            x: []
            for x in PROFIT_COLUMNS
        }),
        height=420,
    )

from typing import Dict, List
import dash_table
import logging
from mytrading.browser.tables.table import create_table
import pandas as pd

active_logger = logging.getLogger(__name__)


def get_runners_table(
        table_id='table-runners',
) -> dash_table.DataTable:
    """get empty mydash DataTable for runner information"""
    return create_table(
        table_id=table_id,
        df=pd.DataFrame({
            'Selection ID': [],
            'Name': [],
            'Starting Odds': []
        }),
    )


def get_runner_id(
        runners_active_cell,
        start_odds: Dict[int, float],
        file_info: List[str]
) -> int:
    """get selection ID of runner from selection cell, or return 0 on fail"""
    if runners_active_cell and 'row' in runners_active_cell:
        row = runners_active_cell['row']
        id_list = list(start_odds.keys())
        if row >= len(id_list):
            logging.warning(f'row {row} in runners out of range for starting odds {start_odds}')
            return 0
        else:
            return id_list[row]
    else:
        file_info.append(f'active cell "{runners_active_cell}" invalid')
        return 0
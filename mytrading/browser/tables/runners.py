from typing import Dict, List
import dash_table
import logging

active_logger = logging.getLogger(__name__)


def get_runners_table(
        id='table-runners',
        height=200,
        width=600
) -> dash_table.DataTable:
    """get empty dash DataTable for runner information"""
    return dash_table.DataTable(
        id=id,
        columns=[{
            'name': x,
            'id': x
        } for x in ['Selection ID', 'Name', 'Starting Odds']],
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
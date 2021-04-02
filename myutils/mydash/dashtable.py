import pandas as pd
from typing import List, Dict


def pad(table_data: List[Dict], page_size) -> None:
    """
    pad a list of dash table dictionary data with empty dicts so the list is at least of `page_size` to maintain a
    constant height
    """
    while len(table_data) == 0 or len(table_data) % page_size != 0:
        table_data.append({})


def datatable_data(df: pd.DataFrame, table_id: str) -> dict:
    """create data kwargs constructing a plotly graph_objects.table"""
    return {
        'id': table_id,
        'columns': [{
            'name': x,
            'id': x
        } for x in df.columns],
        'data': df.to_dict('records')
    }

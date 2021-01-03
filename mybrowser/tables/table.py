import re
from itertools import chain
from os import path
from typing import Iterable, List, Tuple, Dict
import dash_html_components as html
import dash_table
import pandas as pd
import logging

from myutils.mydash import dashtable as mydashtable
from myutils import deepdict


active_logger = logging.getLogger(__name__)


def create_table(
        table_id: str,
        df: pd.DataFrame,
        height,
        padding_top='5px',
        padding_right='30px',
        padding_bottom='5px',
        padding_left='0px',
        text_align='left',
        **table_kwargs
) -> dash_table:
    """
    create a dash datatable in a contained div
     - fixed header, scrollable
     """

    # protect against div by 0 when computing div percentage width
    n_columns = df.shape[1]
    if n_columns == 0:
        active_logger.warning(f'tried to create table with 0 columns')
        return html.Div()

    table_dict = dict(
        **mydashtable.datatable_data(df, table_id),
        style_cell={
            'width': f'{1 / n_columns:.0%}',
            'textAlign': text_align,
        },
        fixed_rows={
            'headers': True,
        },
        style_table={
            'height': height,
        },
    )
    deepdict.dict_update(table_kwargs, table_dict)

    table = dash_table.DataTable(**table_dict)

    return html.Div(
        style={
            'padding': f'{padding_top} {padding_right} {padding_bottom} {padding_left}'
        },
        children=html.Div(
            style={
                'position': 'relative'
            },
            children=table
        )
    )
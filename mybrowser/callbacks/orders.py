from os import path
import dash
from typing import Optional
from dash.dependencies import Output, Input, State
import logging
import pandas as pd
from datetime import datetime

from ..data import DashData
from ..tables.runners import get_runner_id
from ..app import app, dash_data as dd
from .globals import IORegister
from ..cache import cache

from mytrading.tradetracker import orderinfo
from mytrading.tradetracker.messages import MessageTypes
from myutils import generic
from myutils.mydash import intermediate
from myutils import jsonfile
from mytrading.utils import storage
from mytrading.visual import profits
from myutils.mydash import context as my_context


active_logger = logging.getLogger(__name__)
counter = intermediate.Intermediary()

inputs = [
    Input('button-orders', 'n_clicks'),
    Input('button-runners', 'n_clicks'),
    Input('modal-close-orders', 'n_clicks')
]
mid = Output('intermediary-orders', 'children')
IORegister.register_inputs(inputs)
IORegister.register_mid(mid)


def get_profits(p, selection_id) -> Optional[pd.DataFrame]:

    # get order results
    lines = jsonfile.read_file_lines(p)

    # get order infos and check not blank
    lines = [
        ln['order_info'] for ln in lines if
        ln['msg_type'] == MessageTypes.MSG_MARKET_CLOSE.name and
        'order_info' in ln and ln['order_info'] and
        ln['order_info']['order_type']['order_type'] == 'Limit' and
        ln['selection_id'] == selection_id
    ]
    if not lines:
        return pd.DataFrame()

    # lines = [order for order in lines if order['order_type']['order_type'] == 'Limit']

    attrs = {
        'date': 'date_time_created',
        'trade': 'trade.id',
        'side': 'info.side',
        'price': 'order_type.price',
        'size': 'order_type.size',
        'm-price': 'average_price_matched',
        'matched': 'info.size_matched'
    }

    df = pd.DataFrame([
        {
            k: generic.dgetattr(o, v, is_dict=True)
            for k, v in attrs.items()
        } for o in lines
    ])
    df['date'] = df['date'].apply(datetime.fromtimestamp)
    df['order £'] = [orderinfo.dict_order_profit(order) for order in lines]
    return df




@app.callback(
    output=[
        Output('table-orders', 'data'),
        Output('modal-orders', 'is_open'),
        mid,
    ],
    inputs=inputs,
    state=[
        State('table-runners', 'active_cell'),
    ]
)
def update_orders_table(n1, n2, n3, cell):

    orders_pressed = my_context.triggered_id() == 'button-orders'
    r = [
        [],
        False,
        counter.next()
    ]
    if my_context.triggered_id() == 'modal-close-orders':
        return r

    active_logger.info(f'attempting to get orders, active cell: {cell}')

    # if runners button pressed (new active market), clear table
    if not orders_pressed:
        return r

    # if no active market selected then abort
    if not dd.record_list or not dd.db_mkt_info:
        active_logger.warning('no market information/records')
        return r

    # get selection ID of runner from active runner cell, on fail clear table
    if not cell:
        active_logger.warning('no cell selected')
        return r

    if 'row_id' not in cell:
        active_logger.warning(f'row ID not found in active cell info')
        return r

    selection_id = cell['row_id']
    if selection_id not in dd.start_odds:
        active_logger.warning(f'row ID "{selection_id}" not found in starting odds')
        return r

    if not dd.strategy_id:
        active_logger.warning(f'no strategy selected')
        return r

    p = cache.path_strategy_cache(dd.strategy_id, dd.db_mkt_info['market_id'])
    active_logger.info(f'reading strategy market cache file:\n-> {p}')
    if not path.isfile(p):
        active_logger.warning(f'file does not exist')
        return r

    df = get_profits(p, selection_id)
    if not df.shape[0]:
        active_logger.warning(f'Retrieved profits dataframe is empty')
        return r

    # # get order results file from selection ID and check exists
    # f_path = path.join(dd.market_dir, str(selection_id) + storage.EXT_ORDER_RESULT)
    # if not path.isfile(f_path):
    #     active_logger.warning(f'no file "{f_path}" found')
    #     return r
    #
    # # get orders dataframe
    # df = profits.read_profit_table(f_path)
    # if df.shape[0] == 0:
    #     active_logger.warning(f'orders file "{f_path}" empty')
    #     return r

    df = profits.process_profit_table(df, dd.db_mkt_info['market_time'])
    active_logger.info(f'producing orders for {selection_id}, {df.shape[0]} results found"')
    r[0] = df.to_dict('records')
    r[1] = True
    return r

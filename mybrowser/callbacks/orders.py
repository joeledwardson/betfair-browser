from os import path
import dash
from dash.dependencies import Output, Input, State
import logging
from ..data import DashData
from ..tables.runners import get_runner_id
from ..app import app, dash_data as dd
from myutils.mydash import intermediate

from mytrading.utils import storage
from mytrading.visual import profits
from myutils.mydash import context as my_context


active_logger = logging.getLogger(__name__)
counter = intermediate.Intermediary()


@app.callback(
    output=[
        Output('table-orders', 'data'),
        Output('intermediary-orders', 'children')
    ],
    inputs=[
        Input('button-orders', 'n_clicks'),
        Input('button-runners', 'n_clicks'),
    ],
    state=[
        State('table-runners', 'active_cell'),
    ]
)
def update_files_table(orders_clicks, runners_clicks, cell):

    active_logger.info(f'attempting to get orders, active cell: {cell}')
    orders_pressed = my_context.triggered_id() == 'button-orders'
    ret_vals = [list(), counter.next()]

    # if runners button pressed (new active market), clear table
    if not orders_pressed:
        return ret_vals

    # if no active market selected then abort
    if not dd.record_list or not dd.market_info:
        active_logger.warning('no market information/records')
        return ret_vals

    # get selection ID of runner from active runner cell, on fail clear table
    selection_id = get_runner_id(cell, dd.start_odds)
    if not selection_id:
        return ret_vals

    # get order results file from selection ID and check exists
    f_path = path.join(dd.market_dir, str(selection_id) + storage.EXT_ORDER_RESULT)
    if not path.isfile(f_path):
        active_logger.warning(f'no file "{f_path}" found')
        return ret_vals

    # get orders dataframe
    df = profits.read_profit_table(f_path)
    if df.shape[0] == 0:
        active_logger.warning(f'orders file "{f_path}" empty')
        return ret_vals

    df = profits.process_profit_table(df, dd.record_list[0][0].market_definition.market_time)
    active_logger.info(f'producing orders for {selection_id}, {df.shape[0]} results found file "{f_path}"')
    ret_vals[0] = df.to_dict('records')
    return ret_vals

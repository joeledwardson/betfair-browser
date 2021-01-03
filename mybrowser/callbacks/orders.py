from os import path
import dash
from dash.dependencies import Output, Input, State
from ..data import DashData
from ..tables.runners import get_runner_id
from ..text import html_lines

from mytrading.utils import storage
from mytrading.visual import profits
from myutils.mydash import context as my_context


def orders_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('table-orders', 'data'),
            Output('infobox-orders', 'children')
        ],
        inputs=[
            Input('button-orders', 'n_clicks'),
            Input('button-runners', 'n_clicks'),
        ],
        state=[
            State('table-runners', 'active_cell'),
        ]
    )
    def update_files_table(orders_n_clicks, runners_n_clicks, runners_active_cell):

        info_strings = list()
        info_strings.append(f'Active cell: {runners_active_cell}')

        orders_pressed = my_context.triggered_id() == 'button-orders'

        # if runners button pressed (new active market), clear table
        if not orders_pressed:
            return [], html_lines(info_strings)

        # if no active market selected then abort
        if not dd.record_list or not dd.market_info:
            info_strings.append('No market information/records')
            return [], html_lines(info_strings)

        # get selection ID of runner from active runner cell, on fail clear table
        selection_id = get_runner_id(runners_active_cell, dd.start_odds, info_strings)
        if not selection_id:
            return [], html_lines(info_strings)

        # get order results file from selection ID and check exists
        order_file_path = path.join(dd.market_dir, str(selection_id) + storage.EXT_ORDER_RESULT)
        if not path.isfile(order_file_path):
            info_strings.append(f'No file "{order_file_path}" found')
            return [], html_lines(info_strings)

        # get orders dataframe
        df = profits.read_profit_table(order_file_path)
        if df.shape[0] == 0:
            info_strings.append(f'File "{order_file_path}" empty')
            return [], html_lines(info_strings)

        df = profits.process_profit_table(df, dd.record_list[0][0].market_definition.market_time)
        info_strings.append(f'producing orders for {selection_id}, {df.shape[0]} results found')
        info_strings.append(f'data read from "{order_file_path}"')
        return df.to_dict('records'), html_lines(info_strings)
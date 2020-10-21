from os import path
import pandas as pd
import logging
import dash
import dash_html_components as html
from dash.dependencies import Input, Output, State

from mytrading.tradetracker.orderfile import get_order_updates
from mytrading.utils.storage import EXT_ORDER_INFO, EXT_ORDER_RESULT
from mytrading.process.prices import starting_odds
from mytrading.browser.data import DashData
from mytrading.browser.tables.runners import get_runner_id
from mytrading.browser.tables.files import get_files_table, get_table_market
from mytrading.browser.plot import generate_feature_plot
from mytrading.browser.text import html_lines
from mytrading.browser.profit import get_display_profits
from mytrading.visual.profits import process_profit_table, read_profit_table
from myutils.mydash.context import triggered_id
from myutils.generic import dict_sort

active_logger = logging.getLogger(__name__)


def market_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('table-runners', 'data'),
            Output('table-market', 'data'),
            Output('infobox-runners', 'children')
        ],
        inputs=[
            Input('button-runners', 'n_clicks')
        ],
        state=[
            State('table-files', 'active_cell')
        ],
    )
    def runners_pressed(runners_n_clicks, active_cell):
        """
        update data in runners table, and active file indicator when runners button pressed

        :param runners_n_clicks:
        :param active_cell:
        :return:
        """

        file_info = []
        df_runners = pd.DataFrame()
        tbl_market = []

        # try to get record list and market information from active directory (indicated from file_tracker in dash_data)
        success, dd.record_list, dd.market_info = get_table_market(
            dash_data=dd,
            base_dir=input_dir,
            file_info=file_info,
            active_cell=active_cell
        )

        # on fail, success is False and record_list and market_info should be set to none
        if not success:

            # fail - reset selection starting odds and active market directory
            dd.start_odds = {}
            dd.market_dir = ''

        else:

            # success, assign active market directory to dash data instance and compute starting odds
            dd.market_dir = dd.file_tracker.root
            dd.start_odds = dict_sort(starting_odds(dd.record_list))

            df_runners = pd.DataFrame([{
                'Selection ID': k,
                'Name': dd.market_info.names.get(k, ''),
                'Starting Odds': v,
            } for k, v in dd.start_odds.items()])

            # create filenames for order results based on selection IDs
            profit_elements = [
                str(s) + EXT_ORDER_RESULT
                for s in dd.start_odds.keys()
            ]
            # get order result profits (if exist)
            display_profits = get_display_profits(
                dd.file_tracker.root,
                profit_elements
            )
            # add to data frame
            df_runners['Profit'] = display_profits

            tbl_market = [{
                'Attribute': k,
                'Value': getattr(dd.market_info, k)
            } for k in ['event_name', 'market_time', 'market_type']]

        return [
            df_runners.to_dict('records'),
            tbl_market,
            html_lines(file_info)
        ]


def file_table_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('infobox-files-cell', 'children'),
            Output('infobox-path', 'children'),
            Output('table-files-container', 'children')
        ],
        inputs=[
            Input('button-return', 'n_clicks'),
            Input('button-profit', 'n_clicks'),
            Input('table-files', 'active_cell'),
        ],
    )
    def update_files_table(return_n_clicks, profit_n_clicks, active_cell):
        """update active cell indicator, active path indicator, and table for files display based on active cell and if
        return button is pressed"""

        profit_pressed = triggered_id() == 'button-profit'
        return_pressed = triggered_id() == 'button-return'

        # get active directory
        old_root = dd.file_tracker.root
    
        if return_pressed:

            # if return button pressed then navigate to parent directory
            dd.file_tracker.navigate_up()

        elif active_cell is not None:

            # if a cell is pressed, use its row index to navigate to directory (if is directory)
            if 'row' in active_cell:
                dd.file_tracker.navigate_to(active_cell['row'])

        # if directory has changed, then clear the active cell when creating new table
        if dd.file_tracker.root != old_root:
            active_cell = None

        return [
            f'Files active cell: {active_cell}',
            dd.file_tracker.root,
            get_files_table(
                ft=dd.file_tracker,
                base_dir=input_dir,
                do_profits=profit_pressed,
                active_cell=active_cell
            )
        ]
   
    
def figure_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=Output('infobox-figure', 'children'),
        inputs=[
            Input('button-figure', 'n_clicks')
        ],
        state=[
            State('table-runners', 'active_cell')
        ]
    )
    def fig_button(fig_button_clicks, runners_active_cell):

        file_info = list()
        file_info.append(f'Runners active cell: {runners_active_cell}')

        # if no active market selected then abort
        if not dd.record_list or not dd.market_info:
            file_info.append('No market information/records')
            return html_lines(file_info)

        # get selection ID of runner from active runner cell, or abort on fail
        selection_id = get_runner_id(runners_active_cell, dd.start_odds, file_info)
        if not selection_id:
            return html_lines(file_info)

        # get order information from current directory by searching for order info and filtering to selection ID
        orders_df = None
        order_file_path = path.join(dd.market_dir, dd.record_list[0][0].market_id + EXT_ORDER_INFO)
        if path.isfile(order_file_path):
            orders_df = get_order_updates(order_file_path)
            if orders_df.shape[0]:
                orders_df = orders_df[orders_df['selection_id'] == selection_id]

        # make chart title
        title = '{}, name: "{}", ID: "{}"'.format(
            dd.market_info,
            dd.market_info.names.get(selection_id, ""),
            selection_id,
        )

        fig = generate_feature_plot(
            hist_records=dd.record_list,
            selection_id=selection_id,
            display_seconds=90,
            title=title,
            orders_df=orders_df
        )

        fig.show()
        return html_lines(file_info)


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
            State('table-runners', 'active_cell')
        ]
    )
    def update_files_table(orders_n_clicks, runners_n_clicks, runners_active_cell):

        info_strings = [f'Active cell: {runners_active_cell}']

        orders_pressed = triggered_id() == 'button-orders'

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
        order_file_path = path.join(dd.market_dir, str(selection_id) + EXT_ORDER_RESULT)
        if not path.isfile(order_file_path):
            info_strings.append(f'No file "{order_file_path}" found')
            return [], html_lines(info_strings)

        # get orders dataframe
        df = read_profit_table(order_file_path)
        if df.shape[0] == 0:
            info_strings.append(f'File "{order_file_path}" empty')
            return [], html_lines(info_strings)

        df = process_profit_table(df)
        return df.to_dict('records'), html_lines(info_strings)
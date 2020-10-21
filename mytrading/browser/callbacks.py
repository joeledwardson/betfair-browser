from os import path
import pandas as pd

import dash
import dash_html_components as html
from dash.dependencies import Input, Output, State

from mytrading.bf_tradetracker import get_trade_data
from mytrading.utils.storage import EXT_ORDER_INFO, EXT_ORDER_RESULT
from mytrading.process.prices import starting_odds
from myutils.generic import dict_sort
from mytrading.browser.data import DashData
from mytrading.browser.tables.runners import get_runner_id
from mytrading.browser.tables.files import get_files_table, get_table_market
from mytrading.browser.plot import generate_feature_plot
from mytrading.browser.text import html_lines
from mytrading.browser.profit import get_profits, get_display_profits


def market_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('table-runners', 'data'),
            Output('table-market', 'data'),
            Output('file-info', 'children')
        ],
        inputs=[
            Input('runners-button', 'n_clicks')
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

        success, dd.record_list, dd.market_info = get_table_market(
            dash_data=dd,
            base_dir=input_dir,
            file_info=file_info,
            active_cell=active_cell
        )

        if not success:
            dd.start_odds = {}
            dd.market_dir = ''

        else:

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
            html.Div(
                children=html_lines(file_info)
            )
        ]


def file_table_callback(app: dash.Dash, dd: DashData, input_dir: str):
    @app.callback(
        output=[
            Output('active-cell-display', 'children'),
            Output('path-display', 'children'),
            Output('table-files-container', 'children')
        ],
        inputs=[
            Input('return-button', 'n_clicks'),
            Input('profit-button', 'n_clicks'),
            Input('table-files', 'active_cell'),
        ],
    )
    def update_files_table(return_n_clicks, profit_n_clicks, active_cell):
        """update active cell indicator, active path indicator, and table for files display based on active cell and if
        return button is pressed"""
    
        profit_pressed = dd.button_trackers['profit'].update(profit_n_clicks)
        return_pressed = dd.button_trackers['return'].update(return_n_clicks)
    
        old_root = dd.file_tracker.root
    
        if return_pressed:
            dd.file_tracker.navigate_up()
        elif active_cell is not None:
            if 'row' in active_cell:
                dd.file_tracker.navigate_to(active_cell['row'])
    
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
        output=Output('figure-info', 'children'),
        inputs=[
            Input('fig-button', 'n_clicks')
        ],
        state=[
            State('table-runners', 'active_cell')
        ]
    )
    def fig_button(fig_button_clicks, runners_active_cell):

        file_info = list()
        file_info.append(f'Runners active cell: {runners_active_cell}')

        if not dd.record_list or not dd.market_info:
            file_info.append('No market information/records')
            return html_lines(file_info)

        selection_id = get_runner_id(runners_active_cell, dd.start_odds, file_info)
        if not selection_id:
            return html_lines(file_info)

        orders_df = None
        order_file_path = path.join(dd.market_dir, dd.record_list[0][0].market_id + EXT_ORDER_INFO)
        if path.isfile(order_file_path):
            orders_df = get_trade_data(order_file_path)
            if orders_df is not None:
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

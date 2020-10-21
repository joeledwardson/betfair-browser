from __future__ import annotations
import dash
import dash_html_components as html
from os import path
from dash.dependencies import Input, Output, State
import logging
import argparse
from mytrading.bf_tradetracker import get_trade_data
from mytrading.utils.storage import EXT_ORDER_INFO
from mytrading.process.prices import starting_odds
from myutils.generic import dict_sort
from mytrading.browser.data import DashData
from mytrading.browser.tables.runners import get_runner_id
from mytrading.browser.tables.files import get_files_table, get_table_market
from mytrading.browser.plot import generate_feature_plot
from mytrading.browser.text import html_lines
from mytrading.browser.layout import get_layout


parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter  # show defaults in help
)
parser.add_argument(
    'input_dir',
    type=str,
    help='input directory of markets')

args = parser.parse_args()
input_dir = args.input_dir
gdd = DashData(input_dir)

app = dash.Dash(__name__)
logging.basicConfig(level=logging.INFO)
app.layout = get_layout(input_dir, gdd)


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

    profit_pressed = gdd.button_trackers['profit'].update(profit_n_clicks)
    return_pressed = gdd.button_trackers['return'].update(return_n_clicks)

    old_root = gdd.file_tracker.root

    if return_pressed:
        gdd.file_tracker.navigate_up()
    elif active_cell is not None:
        if 'row' in active_cell:
            gdd.file_tracker.navigate_to(active_cell['row'])

    if gdd.file_tracker.root != old_root:
        active_cell = None

    return [
        f'Files active cell: {active_cell}',
        gdd.file_tracker.root,
        get_files_table(
            file_tracker=gdd.file_tracker,
            base_dir=input_dir,
            do_profits=profit_pressed,
            active_cell=active_cell)
    ]


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
    tbl_runners = []
    tbl_market = []

    success, gdd.record_list, gdd.market_info = get_table_market(
        gdd,
        input_dir,
        file_info,
        active_cell)

    if not success:
        gdd.start_odds = {}
        gdd.market_dir = ''

    else:

        gdd.market_dir = gdd.file_tracker.root
        gdd.start_odds = dict_sort(starting_odds(gdd.record_list))

        tbl_runners = [{
            'Selection ID': k,
            'Name': gdd.market_info.names.get(k, ''),
            'Starting Odds': v
        } for k, v in gdd.start_odds.items()]

        tbl_market = [{
            'Attribute': k,
            'Value': getattr(gdd.market_info, k)
        } for k in ['event_name', 'market_time', 'market_type']]

    return [
        tbl_runners,
        tbl_market,
        html.Div(
            children=html_lines(file_info)
        )
    ]


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

    if not gdd.record_list or not gdd.market_info:
        file_info.append('No market information/records')
        return html_lines(file_info)

    selection_id = get_runner_id(runners_active_cell, gdd.start_odds, file_info)
    if not selection_id:
        return html_lines(file_info)

    orders_df = None
    order_file_path = path.join(gdd.market_dir, gdd.record_list[0][0].market_id + EXT_ORDER_INFO)
    if path.isfile(order_file_path):
        orders_df = get_trade_data(order_file_path)
        if orders_df is not None:
            orders_df = orders_df[orders_df['selection_id'] == selection_id]

    # make chart title
    title = '{}, name: "{}", ID: "{}"'.format(
        gdd.market_info,
        gdd.market_info.names.get(selection_id, ""),
        selection_id,
    )

    fig = generate_feature_plot(
        hist_records=gdd.record_list,
        selection_id=selection_id,
        display_seconds=90,
        title=title,
        orders_df=orders_df
    )

    fig.show()

    return html_lines(file_info)


if __name__ == '__main__':
    app.run_server(debug=True)

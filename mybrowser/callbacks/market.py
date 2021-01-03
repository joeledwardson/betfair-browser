import dash
import pandas as pd
from dash.dependencies import Output, Input, State
from typing import List
from betfairlightweight.resources.bettingresources import MarketBook
from datetime import datetime
from ..data import DashData
from ..profit import get_display_profits
from ..tables.market import get_records_market
from ..text import html_lines
from ..marketinfo import MarketInfo

from mytrading.process import prices
from mytrading.utils import storage
from myutils import generic


def add_records_info(info_strings: List[str], record_list: List[List[MarketBook]], market_time: datetime):
    """
    add information about records to info strings
    """

    # TODO - fix width on record display, not working in HTML
    w = 25
    info_strings.append(f'{"first record timestamp":{w}}: {record_list[0][0].publish_time}')
    info_strings.append(f'{"final record timestamp":{w}}: {record_list[-1][0].publish_time}')
    for r in record_list:
        if r[0].market_definition.in_play:
            info_strings.append(f'{"first inplay":{w}}: {r[0].publish_time}')
            break
    else:
        info_strings.append(f'no inplay elements found')
    info_strings.append(f'{"market time":{w}}: {market_time}')


def market_callback(app: dash.Dash, dd: DashData, input_dir: str):
    """
    update runners table and market information table, based on when "get runners" button is clicked
    """
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

        info_strings = []
        df_runners = pd.DataFrame()
        tbl_market = []

        # try to get record list and market information from active directory (indicated from file_tracker in dash_data)
        success, record_list, market_info = get_records_market(
            file_tracker=dd.file_tracker,
            trading=dd.trading,
            base_dir=input_dir,
            file_info=info_strings,
            active_cell=active_cell
        )

        # on fail, success is False and record_list and market_info should be set to none
        if not success:

            # fail - reset record list and market info
            dd.clear_market()

        else:

            # set record list and market info
            dd.record_list = record_list
            dd.market_info = market_info

            # success, assign active market directory to dash data instance and compute starting odds
            dd.market_dir = dd.file_tracker.root
            dd.start_odds = generic.dict_sort(prices.starting_odds(dd.record_list))

            # update info strings with record timings and market time
            add_records_info(info_strings, record_list, market_info.market_time)

            # construct table records with selection ID, names and starting odds
            df_runners = pd.DataFrame([{
                'Selection ID': k,
                'Name': market_info.names.get(k, ''),
                'Starting Odds': v,
            } for k, v in dd.start_odds.items()])

            # create filenames for order results based on selection IDs
            profit_elements = [
                str(s) + storage.EXT_ORDER_RESULT
                for s in dd.start_odds.keys()
            ]

            # get order result profits (if exist)
            display_profits = get_display_profits(
                dd.file_tracker.root,
                profit_elements
            )

            # add to data frame
            df_runners['Profit'] = display_profits

            # create records to pass in callback for table update
            tbl_market = [{
                'Attribute': k,
                'Value': getattr(dd.market_info, k)
            } for k in ['event_name', 'market_time', 'market_type']]

        return [
            df_runners.to_dict('records'),
            tbl_market,
            html_lines(info_strings)
        ]
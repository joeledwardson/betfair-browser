import dash
from dash.dependencies import Output, Input, State
import dash_html_components as html
import pandas as pd
from typing import List
from betfairlightweight.resources.bettingresources import MarketBook
from datetime import datetime
import logging
from ..data import DashData
from ..profit import get_display_profits
from ..tables.market import get_records_market
from ..marketinfo import MarketInfo

from mytrading.process import prices
from mytrading.utils import storage, betfair
from myutils import generic
from myutils.mydash import intermediate


active_logger = logging.getLogger(__name__)
counter = intermediate.Intermediary()


def log_records_info(record_list: List[List[MarketBook]], market_time: datetime):
    """
    add information about records to info strings
    """
    active_logger.info(f'{market_time}, market time')
    active_logger.info(f'{record_list[0][0].publish_time}, first record timestamp')
    active_logger.info(f'{record_list[-1][0].publish_time}, final record timestamp')
    for r in record_list:
        if r[0].market_definition.in_play:
            active_logger.info(f'{r[0].publish_time}, first inplay')
            break
    else:
        active_logger.info(f'no inplay elements found')


def market_callback(app: dash.Dash, dd: DashData, input_dir: str):
    """
    update runners table and market information table, based on when "get runners" button is clicked
    """
    @app.callback(
        output=[
            Output('table-runners', 'data'),
            # Output('table-market', 'data'),
            Output('intermediary-market', 'children'),
            Output('infobox-market', 'children'),
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
        df_runners = pd.DataFrame()
        tbl_market = []

        # try to get record list and market information from active directory (indicated from file_tracker in dash_data)
        success, record_list, market_info = get_records_market(
            file_tracker=dd.file_tracker,
            trading=dd.trading,
            base_dir=input_dir,
            active_cell=active_cell
        )

        # on fail, success is False and record_list and market_info should be set to none
        if not success:

            # fail - reset record list and market info
            dd.clear_market()
            market_description = 'no market loaded'

        else:

            market_description = '{sport} - {event} - {time} - {mkt_type} - {bet_type} - {mkt_id}'.format(
                sport=betfair.event_id_lookup.get(market_info.event_type_id, 'sport unrecognised'),
                event=market_info.event_name,
                time=market_info.market_time,
                mkt_type=market_info.market_type,
                bet_type=market_info.betting_type,
                mkt_id=market_info.market_id,
            )

            # set record list and market info
            dd.record_list = record_list
            dd.market_info = market_info

            # success, assign active market directory to dash data instance and compute starting odds
            dd.market_dir = dd.file_tracker.root
            dd.start_odds = generic.dict_sort(prices.starting_odds(dd.record_list))

            # update info strings with record timings and market time
            log_records_info(record_list, market_info.market_time)

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
            # tbl_market = [{
            #     'Attribute': k,
            #     'Value': getattr(dd.market_info, k)
            # } for k in ['event_name', 'market_time', 'market_type']]

        return [
            df_runners.to_dict('records'),
            # tbl_market,
            counter.next(),
            html.P(market_description)
        ]
import dash
from dash.dependencies import Output, Input, State
import dash_html_components as html
import pandas as pd
from typing import List
from betfairlightweight.resources.bettingresources import MarketBook
from datetime import datetime
import logging
import zlib
from os import path
import os
from ..data import DashData
from ..profit import get_display_profits
from ..tables.market import get_records_market
from ..marketinfo import MarketInfo
from ..config import config
from ..app import app, dash_data as dd
from .globals import IORegister

from mytrading.process import prices
from mytrading.utils import storage, betfair
from myutils import generic
from myutils.mydash import intermediate
from myutils.mydash import dashtable


active_logger = logging.getLogger(__name__)
counter = intermediate.Intermediary()

inputs = [
    Input('button-runners', 'n_clicks')
]
mid = Output('intermediary-runners', 'children')
IORegister.register_inputs(inputs)
IORegister.register_mid(mid)


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


@app.callback(
    output=Output('button-runners', 'disabled'),
    inputs=[
        Input('table-market-db', 'active_cell'),
    ],
)
def runners_pressed(active_cell):
    active_logger.info(f'active cell: {active_cell}')
    if active_cell is not None:
        if 'row_id' in active_cell:
            if active_cell['row_id']:
                return False
    return True


@app.callback(
    output=[
        Output('table-runners', 'data'),
        Output('infobox-market', 'children'),
        mid,
    ],
    inputs=inputs,
    state=[
        State('table-market-db', 'active_cell'),
        State('input-strategy-select', 'value')
    ],
)
def runners_pressed(runners_n_clicks, db_active_cell, strategy_id):
    """
    update runners table and market information table, based on when "get runners" button is clicked
    update data in runners table, and active file indicator when runners button pressed

    :param runners_n_clicks:
    :param active_cell:
    :return:
    """
    empty_tbl = []
    page_size = int(config['TABLE']['page_size'])
    dashtable.pad(empty_tbl, page_size)

    db = dd.betting_db
    ret_fail = (
        empty_tbl,
        html.P('failed to load market'),
        counter.next(),
    )

    if not db_active_cell:
        active_logger.warning(f'no active cell to get market')
        return ret_fail

    market_id = db_active_cell['row_id']
    if not market_id:
        active_logger.warning(f'row ID is blank')
        return ret_fail

    try:
        dd.strategy_id = strategy_id
        if strategy_id:
            strat_dir = path.join(dd.file_tracker.root, 'strategycache', strategy_id)
            strat_path = path.join(strat_dir, market_id)
            strat_path = path.abspath(strat_path)
            if not path.exists(strat_path):
                os.makedirs(strat_dir, exist_ok=True)

                su = db.tables['strategyupdates']
                encoded = db.session.query(
                    su.columns['updates']
                ).filter(
                    su.columns['strategy_id'] == strategy_id,
                    su.columns['market_id'] == market_id
                ).first()
                decoded = encoded[0].decode()
                active_logger.info(f'writing strategy market updates to cache: "{strat_path}"')
                with open(strat_path, 'w') as f:
                    f.write(decoded)

        cache_dir = path.join(dd.file_tracker.root, 'marketcache')
        if not path.isdir(cache_dir):
            os.makedirs(cache_dir)
        p = path.join(cache_dir, market_id)

        if not path.exists(p):
            active_logger.info(f'writing market to cache file: "{p}"')
            r = db.session.query(
                db.tables['marketstream'].columns['data']
            ).filter(
                db.tables['marketstream'].columns['market_id'] == market_id
            ).first()
            data = zlib.decompress(r[0]).decode()
            with open(p, 'w') as f:
                f.write(data)

        active_logger.info(f'reading market from cache file: "{p}"')
        q = storage.get_historical(dd.trading, p)
        dd.record_list = list(q.queue)

        sr = db.tables['strategyrunners']
        cte_strat = db.session.query(
            sr.columns['runner_id'],
            sr.columns['profit'].label('runner_profit')
        ).filter(
            sr.columns['strategy_id'] == strategy_id,
            sr.columns['market_id'] == market_id
        ).cte()

        rn = db.tables['runners']
        rows = db.session.query(
            rn,
            cte_strat.c['runner_profit'],
        ).join(
            cte_strat,
            rn.columns['runner_id'] == cte_strat.c['runner_id'],
            isouter=True,
        ).filter(
            rn.columns['market_id'] == market_id
        ).all()

        meta = db.session.query(
            db.tables['marketmeta']
        ).filter(
            db.tables['marketmeta'].columns['market_id'] == market_id
        ).first()

        dd.db_mkt_info = dict(meta)
        dd.start_odds = generic.dict_sort(prices.starting_odds(dd.record_list))

        dd.runner_names = {
            dict(r)['runner_id']: dict(r)['runner_name']
            for r in rows
        }

        runner_infos = [dict(r) for r in rows]

        tbl_data = [{
            'id': d['runner_id'], # set row to ID for easy access in callbacks
            'Selection ID': d['runner_id'],
            'Name': d['runner_name'] or d['runner_id'],
            'Starting Odds': dd.start_odds.get(d['runner_id'], 999),
            'Profit': d['runner_profit']
        } for d in runner_infos]

        dashtable.pad(tbl_data, page_size)

        # columns['runner_namesfilter('db.Meta.betfair_id == row_id).first()
        # tbl_data = [{
        #     'Selection ID': dict(r)['runner_id'],
        #     'Name': dict(r)['runner_name']
        # } for r in rows]

        return (
            tbl_data,
            html.P(f'loaded "{market_id}"'),
            counter.next(),
        )
    except Exception as e:
        active_logger.warning(f'failed getting runner names: {e}', exc_info=True)
        return ret_fail

    # # try to get record list and market information from active directory (indicated from file_tracker in dash_data)
    # success, record_list, market_info = get_records_market(
    #     file_tracker=dd.file_tracker,
    #     trading=dd.trading,
    #     base_dir=input_dir,
    #     active_cell=active_cell
    # )
    #
    # # on fail, success is False and record_list and market_info should be set to none
    # if not success:
    #
    #     # fail - reset record list and market info
    #     dd.clear_market()
    #     market_description = 'no market loaded'
    #
    # else:
    #
    #     market_description = '{sport} - {event} - {time} - {mkt_type} - {bet_type} - {mkt_id}'.format(
    #         sport=betfair.event_id_lookup.get(market_info.event_type_id, 'sport unrecognised'),
    #         event=market_info.event_name,
    #         time=market_info.market_time,
    #         mkt_type=market_info.market_type,
    #         bet_type=market_info.betting_type,
    #         mkt_id=market_info.market_id,
    #     )
    #
    #     # set record list and market info
    #     dd.record_list = record_list
    #     dd.market_info = market_info
    #
    #     # success, assign active market directory to dash data instance and compute starting odds
    #     dd.market_dir = dd.file_tracker.root
    #     dd.start_odds = generic.dict_sort(prices.starting_odds(dd.record_list))
    #
    #     # update info strings with record timings and market time
    #     log_records_info(record_list, market_info.market_time)
    #
    #     # construct table records with selection ID, names and starting odds
    #     df_runners = pd.DataFrame([{
    #         'Selection ID': k,
    #         'Name': market_info.names.get(k, ''),
    #         'Starting Odds': v,
    #     } for k, v in dd.start_odds.items()])
    #
    #     # create filenames for order results based on selection IDs
    #     profit_elements = [
    #         str(s) + storage.EXT_ORDER_RESULT
    #         for s in dd.start_odds.keys()
    #     ]
    #
    #     # get order result profits (if exist)
    #     display_profits = get_display_profits(
    #         dd.file_tracker.root,
    #         profit_elements
    #     )
    #
    #     # add to data frame
    #     df_runners['Profit'] = display_profits
    #
    #     # create records to pass in callback for table update
    #     # tbl_market = [{
    #     #     'Attribute': k,
    #     #     'Value': getattr(dd.market_info, k)
    #     # } for k in ['event_name', 'market_time', 'market_type']]
    #
    # return [
    #     df_runners.to_dict('records'),
    #     # tbl_market,
    #     counter.next(),
    #     html.P(market_description)
    # ]



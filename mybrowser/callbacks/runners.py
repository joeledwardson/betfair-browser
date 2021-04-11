import dash
from dash.dependencies import Output, Input, State
import dash_html_components as html
from betfairlightweight.resources.bettingresources import MarketBook
from datetime import datetime
import logging
from typing import Optional, List, Dict
from os import path
from betfairlightweight.exceptions import BetfairError
from flumine.exceptions import FlumineException
from sqlalchemy.exc import SQLAlchemyError

from ..app import app, dash_data as dd
from .. import bfcache

from mytrading.process import prices
from mytrading.utils import storage, betfair
from myutils import generic
from myutils.mydash import intermediate
from myutils.mydash import context

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = intermediate.Intermediary()


def read_market_cache(p, trading) -> Optional[List[List[MarketBook]]]:
    """
    read streamed market from cache file, return None on fail
    """

    active_logger.info(f'reading market cache file:\n-> {p}')

    if not path.isfile(p):
        active_logger.warning(f'file does not exist')
        return None

    try:
        q = storage.get_historical(trading, p)
    except (FlumineException, BetfairError) as e:
        active_logger.warning(f'failed to read market file\n{e}', exc_info=True)
        return None

    l = list(q.queue)
    if not len(l):
        active_logger.warning(f'market cache file is empty')
        return None

    return l


def log_records_info(record_list: List[List[MarketBook]], market_time: datetime):
    """
    log information about records
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


# TODO - move all database specific functions into own module? Make database BettingDB object global in database
#  interface file (and private) so that all database access should be through functions without direct access - also
#  move cache to database package
def runner_rows(db, market_id, strategy_id):
    """
    get filters rows of runners, joined with profit column from strategy
    """
    sr = db.tables['strategyrunners']
    cte_strat = db.session.query(
        sr.columns['runner_id'],
        sr.columns['profit'].label('runner_profit')
    ).filter(
        sr.columns['strategy_id'] == strategy_id,
        sr.columns['market_id'] == market_id
    ).cte()

    rn = db.tables['runners']
    return db.session.query(
        rn,
        cte_strat.c['runner_profit'],
    ).join(
        cte_strat,
        rn.columns['runner_id'] == cte_strat.c['runner_id'],
        isouter=True,
    ).filter(
        rn.columns['market_id'] == market_id
    ).all()


def market_meta(db, market_id):
    """
    get meta information about a market
    """
    return db.session.query(
        db.tables['marketmeta']
    ).filter(
        db.tables['marketmeta'].columns['market_id'] == market_id
    ).first()


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
        Output('intermediary-runners', 'children'),
        Output('loading-out-runners', 'children')
    ],
    inputs=[
        Input('button-runners', 'n_clicks')
    ],
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

    db = dd.betting_db
    ret = [
        [],  # empty table
        html.P('failed to load market'),
        counter.next(),
        ''
    ]

    # first callback call
    if not runners_n_clicks:
        ret[1] = 'no market selected'
        return ret

    if not db_active_cell:
        active_logger.warning(f'no active cell to get market')
        return ret

    market_id = db_active_cell['row_id']
    if not market_id:
        active_logger.warning(f'row ID is blank')
        return ret

    # check strategy valid if one is selected, when writing info to cache
    dd.strategy_id = strategy_id
    if strategy_id:
        if not bfcache.w_strat(strategy_id, market_id, db):
            return ret

    # check market stream is valid when writing to cache
    if not bfcache.w_mkt(market_id, db):
        return ret

    # read market stream back from cache and check valid
    p = bfcache.p_mkt(market_id)
    dd.record_list = read_market_cache(p, dd.trading)
    if not dd.record_list:
        return ret

    # get runner name/profit and market metadata from db
    try:
        rows = runner_rows(db, market_id, strategy_id)
        meta = market_meta(db, market_id)
    except SQLAlchemyError as e:
        active_logger.warning(f'failed getting runners rows/market meta from DB: {e}', exc_info=True)
        return ret

    # put market information into dash data
    dd.db_mkt_info = dict(meta)
    dd.start_odds = generic.dict_sort(prices.starting_odds(dd.record_list))
    dd.runner_names = {
        dict(r)['runner_id']: dict(r)['runner_name']
        for r in rows
    }

    # set runner table sorted by starting odds and market information string in returned values
    runner_infos = [dict(r) for r in rows]
    tbl = [{
        'id': d['runner_id'],  # set row to ID for easy access in callbacks
        'Selection ID': d['runner_id'],
        'Name': d['runner_name'] or d['runner_id'],
        'Starting Odds': dd.start_odds.get(d['runner_id'], 999),
        'Profit': d['runner_profit']
    } for d in runner_infos]
    ret[0] = sorted(tbl, key=lambda d: d['Starting Odds'])
    ret[1] = f'loaded "{market_id}"'
    return ret


@app.callback(
    Output("left-side-bar", "className"),
    [
        Input("btn-runners-filter", "n_clicks"),
        Input("btn-left-close", "n_clicks")
    ],
)
def toggle_classname(n1, n2):
    if context.triggered_id() == 'btn-runners-filter':
        return "left-not-collapsed"
    else:
        return ""


@app.callback(
    [Output('button-figure', 'disabled'), Output('button-orders', 'disabled')],
    Input('table-runners', 'active_cell')
)
def fig_btn_disable(active_cell):
    if active_cell is not None and 'row_id' in active_cell:
        return False, False
    else:
        return True, True


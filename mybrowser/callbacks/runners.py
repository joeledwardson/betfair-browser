from dash.dependencies import Output, Input, State
import dash_html_components as html
import logging
from typing import List

from ..app import app, dash_data as dd
from myutils.mydash import intermediate
from myutils.mydash import context


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = intermediate.Intermediary()


@app.callback(
    output=Output('button-runners', 'disabled'),
    inputs=[
        Input('table-market-db', 'active_cell'),
    ],
)
def btn_disable(active_cell):
    active_logger.info(f'active cell: {active_cell}')
    if active_cell is not None:
        if 'row_id' in active_cell:
            if active_cell['row_id']:
                return False
    return True


# TODO - move all market selection processing to dashdata (user session) class to separate from dash processing
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

    if not dd.load_market(market_id, strategy_id):
        return ret

    tbl = [{
        'id': d['runner_id'],  # set row to ID for easy access in callbacks
        'Selection ID': d['runner_id'],
        'Name': d['runner_name'] or d['runner_id'],
        'Starting Odds': dd.start_odds.get(d['runner_id'], 999),
        'Profit': d['runner_profit']
    } for d in dd.runner_infos]

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


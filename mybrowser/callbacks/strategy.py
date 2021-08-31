from __future__ import annotations
from dash.dependencies import Output, Input, State
import dash_html_components as html

import json
from typing import List, Dict, Any, Optional
from myutils import dashutils
import logging
from ..session import Session, post_notification
from mytrading.strategy import tradetracker as tt

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)



def cb_strategy(app, shn: Session):
    @app.callback(
        Output("strategy-delete-modal", "is_open"),
        [
            Input("btn-strategy-delete", "n_clicks"),
            Input("strategy-delete-yes", "n_clicks"),
            Input("strategy-delete-no", "n_clicks")
        ], [
            State("strategy-delete-modal", "is_open")
        ],
    )
    def toggle_modal(n1, n2, n3, is_open):
        if n1 or n2 or n3:
            return not is_open
        return is_open

    @app.callback(
        output=[
            Output('table-strategies', 'data'),
            Output('table-strategies', "selected_cells"),
            Output('table-strategies', 'active_cell'),
            Output('table-strategies', 'page_current'),
            Output('notifications-strategy', 'data')
        ],
        inputs=[
            Input('btn-strategy-refresh', 'n_clicks'),
            Input('strategy-delete-yes', 'n_clicks'),
        ],
        state=[
            State('table-strategies', 'active_cell')
        ]
    )
    def strat_intermediary(
            n_refresh,
            n_delete,
            active_cell,
    ):
        notifs = []
        btn_id = dashutils.triggered_id()
        strategy_id = active_cell['row_id'] if active_cell and 'row_id' in active_cell else None

        # delete strategy if requested
        if btn_id == 'strategy-delete-yes':
            if not strategy_id:
                post_notification(notifs, 'warning', 'Strategy', 'Must select a strategy to delete')
            else:
                n0, n1, n2 = shn.betting_db.strategy_delete(strategy_id)
                msg = f'removed {n0} strategy meta, {n1} markets, {n2} runners'
                post_notification(notifs, 'info', 'Strategy', msg)

        post_notification(notifs, 'info', 'Strategy', 'Strategies reloaded')
        tbl_rows = shn.strats_tbl_rows()
        for r in tbl_rows:
            r['id'] = r['strategy_id']  # assign 'id' so market ID set in row ID read in callbacks
        return [
            tbl_rows,  # table rows data
            [],  # clear selected cell(s)
            None,  # clear selected cell
            0,  # reset current page back to first page
            notifs
        ]

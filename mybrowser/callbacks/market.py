from __future__ import annotations
from dash.dependencies import Output, Input, State
import dash_html_components as html

import json
from typing import List, Dict, Any, Optional
from myutils import dashutils
import logging
from ..session import Session, Notification as Notif, NotificationType as NType
from mytrading.strategy import tradetracker as tt

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = dashutils.Intermediary()
strat_counter = dashutils.Intermediary()


def cb_market(app, shn: Session):
    @app.callback(
        output=[
            Output('progress-container-div', 'hidden'),
            Output('header-progress-bar', 'children'),
            Output('header-progress-bar', 'value')
        ],
        inputs=[
            Input('interval-component', 'n_intervals')
        ]
    )
    def int_callback(n_intervals):
        if not shn.strat_running:
            return True, None, None
        else:
            n_mkts = shn.strat_mkt_count
            n_done = shn.strat_n_done
            return (
                False,
                f'{n_done}/{n_mkts}',
                max(n_done/n_mkts*100, 10)  # minimum width is 20% so can see text
            )

    @app.callback(
        output=Output('market-sorter', 'value'),
        inputs=Input('btn-sort-clear', 'n_clicks'),
    )
    def market_sort_clear(n_clicks):
        return None

    @app.callback(
        output=[
            Output('market-query-status', 'children'),
            Output('table-market-session', 'data'),
            Output('table-market-session', "selected_cells"),
            Output('table-market-session', 'active_cell'),
            Output('table-market-session', 'page_current'),
            Output('loading-out-session', 'children'),
            Output('intermediary-session-market', 'children'),

            Output('input-sport-type', 'value'),
            Output('input-mkt-type', 'value'),
            Output('input-bet-type', 'value'),
            Output('input-format', 'value'),
            Output('input-country-code', 'value'),
            Output('input-venue', 'value'),
            Output('input-date', 'value'),
            Output('input-mkt-id', 'value'),

            Output('input-sport-type', 'options'),
            Output('input-mkt-type', 'options'),
            Output('input-bet-type', 'options'),
            Output('input-format', 'options'),
            Output('input-country-code', 'options'),
            Output('input-venue', 'options'),
            Output('input-date', 'options')
        ],
        inputs=[
            Input('input-mkt-clear', 'n_clicks'),
            Input('input-strategy-clear', 'n_clicks'),
            Input('btn-cache-clear', 'n_clicks'),
            Input('btn-db-refresh', 'n_clicks'),
            Input('btn-db-upload', 'n_clicks'),
            Input('btn-db-reconnect', 'n_clicks'),
            Input('btn-strategy-run', 'n_clicks'),
            Input('market-sorter', 'value'),
            Input('btn-strategy-download', 'n_clicks'),

            Input('input-sport-type', 'value'),
            Input('input-mkt-type', 'value'),
            Input('input-bet-type', 'value'),
            Input('input-format', 'value'),
            Input('input-country-code', 'value'),
            Input('input-venue', 'value'),
            Input('input-date', 'value'),
            Input('input-mkt-id', 'value')
        ],
        state=[
            State('input-strategy-run', 'value'),
            State('table-strategies', 'active_cell')
        ]
    )
    def mkt_intermediary(
            n_mkt_clear,
            n_strat_clear,
            n_cache_clear,
            n_db_refresh,
            n_db_upload,
            n_db_reconnect,
            n_strat_run,
            market_sorter,
            n_strat_download,
            m0, m1, m2, m3, m4, m5, m6, m7,
            strategy_run_val,
            strategy_tbl_cell,
    ):
        flt_market_args = [m0, m1, m2, m3, m4, m5, m6, m7]
        btn_id = dashutils.triggered_id()
        shn.notif_post(Notif(NType.INFO, 'Market Database', 'Updated markets'))

        # run new strategy if requested
        if btn_id == 'btn-strategy-run':
            shn.strat_update()  # update configurations first
            if strategy_run_val is None:
                shn.notif_post(Notif(NType.WARNING, 'Strategy', 'cannot run strategy without selecting one'))
            else:
                strategy_id = str(shn.strat_run(strategy_run_val))
                shn.notif_post(Notif(NType.INFO, 'Strategy', f'created new strategy "{strategy_id}"'))
                shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits)  # upload strategy from cache

        # wipe cache if requested
        if btn_id == 'btn-cache-clear':
            n_files, n_dirs = shn.betting_db.wipe_cache()
            shn.notif_post(Notif(NType.INFO, 'Cache', f'Cleared {n_files} files and {n_dirs} dirs from cache'))

        # TODO - move all strategy functions from here to strategy page
        # reconnect to database if button pressed
        if btn_id == 'btn-db-reconnect':
            shn.rl_db()
            shn.notif_post(Notif(NType.INFO, 'Database', 'reconnected to database'))

        # upload market & strategy cache if "upload" button clicked
        if btn_id == 'btn-db-upload':
            n_mkt = len(shn.betting_db.scan_mkt_cache())
            n_strat = len(shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits))
            shn.notif_post(Notif(NType.INFO, 'Cache', f'found {n_mkt} new markets in cache'))
            shn.notif_post(Notif(NType.INFO, 'Cache', f'found {n_strat} new strategies in cache'))

        # update strategy filters and selectable options
        if btn_id == 'btn-strategy-download':
            if 'row_id' not in strategy_tbl_cell:
                shn.notif_post(Notif(NType.WARNING, 'Strategy', 'no row ID found in strategy cell'))
                shn.active_strat_set(None)
            else:
                shn.active_strat_set(strategy_tbl_cell['row_id'])
        # clear strategy ID variable used in market filtering if "clear strategy" button clicked
        if btn_id in ['input-strategy-clear', 'btn-db-reconnect', 'btn-strategy-delete']:
            shn.active_strat_set(None)
        # shn.filters_strat.update_filters(clear=strat_clear, args=[shn.active_strat_get()])
        # strat_cte = shn.betting_db.filters_strat_cte(shn.filters_strat)
        # strat_vals = shn.filters_strat.filters_values()
        # strat_lbls = shn.betting_db.filters_labels(shn.filters_strat, strat_cte)

        # update market filters and selectable options
        mkt_clear = btn_id in ['input-mkt-clear', 'btn-db-reconnect']
        shn.filters_mkt.update_filters(clear=mkt_clear, args=flt_market_args)

        cte = shn.betting_db.filters_mkt_cte(shn.active_strat_get(), shn.filters_mkt)
        vals = shn.filters_mkt.filters_values()
        lbls = shn.betting_db.filters_labels(shn.filters_mkt, cte)
        if btn_id == 'btn-sort-clear':
            market_sorter = None
        if market_sorter:
            dropdown_dict = json.loads(market_sorter)
            order_col = dropdown_dict.get('db_col')
            order_asc = dropdown_dict.get('asc')
        else:
            order_col, order_asc = None, None
        # query db with filtered CTE to generate table rows for display
        tbl_rows = shn.mkt_tbl_rows(cte, order_col, order_asc)
        # assign 'id' so market ID set in row ID read in callbacks
        for r in tbl_rows:
            r['id'] = r['market_id']

        # generate status string of markets/strategies available and strategy selected
        n = shn.betting_db.cte_count(cte)
        ns = shn.betting_db.strategy_count()
        q_sts = [
            html.Div(f'Showing {len(tbl_rows)} of {n} available, {ns} strategies available'),
            html.Div(
                f'strategy ID: {shn.active_strat_get()}'
                if shn.active_strat_get() is not None else 'No strategy selected'
            )
        ]

        # combine all outputs together
        return [
            q_sts,  # table query status
            tbl_rows,  # set market table row data
            [],  # clear selected cell(s)
            None,  # clear selected cell
            0,  # reset current page back to first page
            '',  # loading output
            counter.next(),  # intermediary counter value
            # market_sorter  # market sorter value
        ] + vals + lbls

    @app.callback(
        [
            Output('input-strategy-run', 'options'),
            Output('intermediary-strat-reload', 'children')
        ],
        Input('btn-strategies-reload', 'n_clicks')
    )
    def strategy_run_reload(n_reload):
        n_confs = len(shn.strat_update())
        shn.notif_post(Notif(NType.INFO, 'Strategy Configs', f'loaded {n_confs} strategy configs'))

        options = [{
            'label': v,
            'value': v
        } for v in shn.strat_cfg_names]

        return [
            options,
            strat_counter.next()
        ]

    @app.callback(
        Output('btn-strategy-run', 'disabled'),
        Input('input-strategy-run', 'value')
    )
    def strategy_run_enable(strategy_run_select):
        return strategy_run_select is None



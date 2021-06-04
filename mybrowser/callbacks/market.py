from __future__ import annotations
from dash.dependencies import Output, Input, State
import dash_html_components as html

from typing import List, Dict, Any, Optional
from myutils import mydash
import logging
from ..session import Session
from mytrading.strategy import tradetracker as tt

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = mydash.Intermediary()


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
        output=[
            Output('market-query-status', 'children'),
            Output('table-market-session', 'data'),
            Output('table-market-session', "selected_cells"),
            Output('table-market-session', 'active_cell'),
            Output('table-market-session', 'page_current'),
            Output('loading-out-session', 'children'),
            Output('intermediary-session-market', 'children'),
            Output('toast-db-market', 'is_open'),
            Output('toast-db-market', 'children'),

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
            Output('input-date', 'options'),

            Output('input-strategy-select', 'value'),
            Output('input-strategy-select', 'options'),
        ],
        inputs=[
            Input('input-mkt-clear', 'n_clicks'),
            Input('input-strategy-clear', 'n_clicks'),
            Input('btn-strategy-delete', 'n_clicks'),
            Input('table-market-session', 'sort_mode'),
            Input('btn-cache-clear', 'n_clicks'),
            Input('btn-db-refresh', 'n_clicks'),
            Input('btn-db-upload', 'n_clicks'),
            Input('btn-db-reconnect', 'n_clicks'),
            Input('btn-strategy-run', 'n_clicks'),

            Input('input-strategy-select', 'value'),

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
            State('input-strategy-run', 'value')
        ]
    )
    def mkt_intermediary(
            n_mkt_clear,
            n_strat_clear,
            n_strat_del,
            sort_mode,
            n_cache_clear,
            n_db_refresh,
            n_db_upload,
            n_db_reconnect,
            n_strat_run,
            strategy_id,
            m0, m1, m2, m3, m4, m5, m6, m7,
            strategy_run_val
    ):
        flt_market_args = [m0, m1, m2, m3, m4, m5, m6, m7]
        btn_id = mydash.triggered_id()

        toast_open = True
        toast_msg = 'Updated markets from database'

        # run new strategy if requested
        if btn_id == 'btn-strategy-run':
            shn.strat_update()  # update configurations first
            if strategy_run_val is None:
                toast_msg = 'cannot run strategy without selecting one'
            else:
                strategy_id = str(shn.strat_run(strategy_run_val))
                toast_msg = f'created new strategy "{strategy_id}'
                shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits)  # upload strategy from cache

        # wipe cache if requested
        if btn_id == 'btn-cache-clear':
            n_files, n_dirs = shn.betting_db.wipe_cache()
            toast_msg = f'Cleared {n_files} files and {n_dirs} dirs from cache'

        # delete strategy if requested
        if btn_id == 'btn-strategy-delete':
            if not strategy_id:
                toast_msg = 'must select strategy first'
            else:
                n0, n1, n2 = shn.betting_db.strategy_delete(strategy_id)
                toast_msg = f'removed {n0} strategy meta, {n1} markets, {n2} runners'

        # reconnect to database if button pressed
        if btn_id == 'btn-db-reconnect':
            shn.rl_db()
            toast_msg = 'reconnected to database'

        # upload market & strategy cache if "upload" button clicked
        if btn_id == 'btn-db-upload':
            n_mkt = len(shn.betting_db.scan_mkt_cache())
            n_strat = len(shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits))
            toast_msg = f'found {n_mkt} new markets and {n_strat} new strategies in cache'

        # update strategy filters and selectable options
        strat_clear = btn_id in ['input-strategy-clear', 'btn-db-reconnect', 'btn-strategy-delete']
        shn.filters_strat.update_filters(clear=strat_clear, args=[strategy_id])
        strat_cte = shn.betting_db.filters_strat_cte(shn.filters_strat)
        strat_vals = shn.filters_strat.filters_values()
        strat_lbls = shn.betting_db.filters_labels(shn.filters_strat, strat_cte)

        # update market filters and selectable options
        mkt_clear = btn_id in ['input-mkt-clear', 'btn-db-reconnect']
        shn.filters_mkt.update_filters(clear=mkt_clear, args=flt_market_args)
        # clear strategy ID variable used in market filtering if "clear strategy" button clicked
        if strat_clear:
            strategy_id = None
        cte = shn.betting_db.filters_mkt_cte(strategy_id, shn.filters_mkt)
        vals = shn.filters_mkt.filters_values()
        lbls = shn.betting_db.filters_labels(shn.filters_mkt, cte)
        tbl_rows = shn.filters_mkt_tbl(cte)  # query db with filtered CTE to generate table rows for display
        for r in tbl_rows:
            r['id'] = r['market_id']  # assign 'id' so market ID set in row ID read in callbacks

        # generate status string of markets/strategies available and strategy selected
        n = shn.betting_db.cte_count(cte)
        ns = shn.betting_db.strategy_count()
        q_sts = [
            html.Div(f'Showing {len(tbl_rows)} of {n} available, {ns} strategies available'),
            html.Div(
                f'strategy ID={strategy_id}'
                if strategy_id is not None else 'no strategy selected'
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
            toast_open,
            toast_msg
        ] + vals + lbls + strat_vals + strat_lbls

    @app.callback([
        Output('input-strategy-run', 'options'),
        Output('toast-strat-reload', 'is_open'),
        Output('toast-strat-reload', 'children')
    ], Input('btn-strategies-reload', 'n_clicks'))
    def strategy_run_reload(n_reload):
        n_confs = len(shn.strat_update())
        options = [{
            'label': v,
            'value': v
        } for v in shn.strat_cfg_names]
        return [
            options,
            True,
            f'loaded {n_confs} strategy configs'
        ]

    @app.callback(Output('btn-strategy-run', 'disabled'), Input('input-strategy-run', 'value'))
    def strategy_run_enable(strategy_run_select):
        return strategy_run_select is None

    @app.callback(Output('btn-strategy-delete', 'disabled'), Input('input-strategy-select', 'value'))
    def strategy_delete_enable(strategy_id):
        return strategy_id is None

    @app.callback(
        Output("container-filters-market", "className"),
        [
            Input("btn-session-filter", "n_clicks"),
            Input("btn-right-close", "n_clicks")
        ],
        State("container-filters-market", "className")
    )
    def toggle_classname(n1, n2, class_names: str):
        # CSS class toggles sidebar
        classes = mydash.CSSClassHandler(class_names)
        if mydash.triggered_id() == 'btn-session-filter':
            return str(classes + "right-not-collapsed")
        else:
            return str(classes - "right-not-collapsed")


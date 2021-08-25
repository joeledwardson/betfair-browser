from __future__ import annotations
from dash.dependencies import Output, Input, State
import dash_html_components as html

import json
from typing import List, Dict, Any, Optional
from myutils.dashutils import Config, TDict, Intermediary, dict_callback, triggered_id
from mytrading.utils.dbfilter import filters_reg
import logging
from ..session import Session, post_notification
from ..layouts.market import FILTERS
from mytrading.strategy import tradetracker as tt

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = Intermediary()
strat_counter = Intermediary()


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

    def market_callback(outputs: TDict, inputs: TDict, states: TDict):
        btn_id = triggered_id()
        notifs = []
        strategy_id = states['strategy-id']

        # # run new strategy if requested
        # if btn_id == 'btn-strategy-run':
        #     shn.strat_update()  # update configurations first
        #     if strategy_run_val is None:
        #         post_notification(notifs, 'warning', 'Strategy', 'cannot run strategy without selecting one')
        #     else:
        #         strategy_id = str(shn.strat_run(strategy_run_val))
        #         post_notification(notifs, 'info', 'Strategy', f'created new strategy "{strategy_id}"')
        #         shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits)  # upload strategy from cache

        # wipe cache if requested
        if btn_id == 'btn-cache-clear':
            n_files, n_dirs = shn.betting_db.wipe_cache()
            post_notification(notifs, 'info', 'Cache', f'Cleared {n_files} files and {n_dirs} dirs from cache')

        # TODO - move all strategy functions from here to strategy page
        # reconnect to database if button pressed
        if btn_id == 'btn-db-reconnect':
            shn.rl_db()
            post_notification(notifs, 'info', 'Database', 'reconnected to database')

        # upload market & strategy cache if "upload" button clicked
        if btn_id == 'btn-db-upload':
            n_mkt = len(shn.betting_db.scan_mkt_cache())
            n_strat = len(shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits))
            post_notification(notifs, 'info', 'Cache', f'found {n_mkt} new markets in cache')
            post_notification(notifs, 'info', 'Cache', f'found {n_strat} new strategies in cache')

        # update strategy filters and selectable options
        if btn_id == 'btn-strategy-download':
            strategy_cell = states['strategy-cell']
            if 'row_id' not in strategy_cell:
                post_notification(notifs, 'warning', 'Strategy', 'no row ID found in strategy cell')
                strategy_id = None
            else:
                strategy_id = strategy_cell['row_id']

        # clear strategy ID variable used in market filtering if "clear strategy" button clicked
        if btn_id in ['input-strategy-clear', 'btn-db-reconnect', 'btn-strategy-delete']:
            post_notification(notifs, 'info', 'Strategy', 'strategy cleared')
            strategy_id = None

        # update market filters and selectable options
        clear = btn_id in ['input-mkt-clear', 'btn-db-reconnect']
        filter_inputs = inputs['filter-inputs']
        filter_inputs = {k: None if clear else v for k, v in filter_inputs.items()}
        # shn.betting_db.meta_de_serialise(filter_inputs)
        column_filters = shn.market_filter_conditions(list(filter_inputs.values()))

        # shn.filters_mkt.update_filters(clear=mkt_clear, args=flt_market_args)
        cte = shn.betting_db.filters_mkt_cte(strategy_id, column_filters)
        # vals = shn._flts_mkt
        # vals = shn.filters_mkt.filters_values()
        # lbls = shn.betting_db.filters_labels(shn.filters_mkt, cte)

        market_sorter = inputs['sorter']
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
        post_notification(notifs, 'info', 'Market Database', f'Showing {n} markets')

        outputs['query-status'] = [
            html.Div(f'Showing {len(tbl_rows)} of {n} available, {ns} strategies available'),
            html.Div(
                f'strategy ID: {strategy_id}'
                if strategy_id is not None else 'No strategy selected'
            )
        ] # table query status
        outputs['table-data'] = tbl_rows # set market table row data
        outputs['table-selected-cells'] = [] # clear selected cell(s)
        outputs['table-active-cell'] = None  # clear selected cell(s)
        outputs['table-current-page'] = 0  # reset current page back to first page
        outputs['loading'] = '' # blank loading output
        outputs['intermediary'] = counter.next()  # intermediary counter value
        outputs['notifications'] = notifs
        outputs['strategy-id'] = strategy_id
        outputs['filter-values'] = list(filter_inputs.values())
        outputs['filter-options'] = shn.betting_db.filters_labels(shn.filters_mkt, cte)

        # combine all outputs together
        # return [
        #            q_sts,  # table query status
        #            tbl_rows,  # set market table row data
        #            [],
        #            None,  # clear selected cell
        #            0,  # reset current page back to first page
        #            '',
        #            counter.next(),  # intermediary counter value
        #            notifs,
        #            # market_sorter  # market sorter value
        #        ] + vals + lbls

    dict_callback(
        app=app,
        outputs_config={
            'query-status': Output('market-query-status', 'children'),
            'table-data': Output('table-market-session', 'data'),
            'table-selected-cells': Output('table-market-session', "selected_cells"),
            'table-active-cell': Output('table-market-session', 'active_cell'),
            'table-current-page': Output('table-market-session', 'page_current'),
            'loading': Output('loading-out-session', 'children'),
            'intermediary': Output('intermediary-session-market', 'children'),
            'notifications': Output('notifications-market', 'data'),
            'strategy-id': Output('selected-strategy', 'data'),
            'filter-values': [
                Output(f['layout']['id'], 'value')
                for f in FILTERS if 'filter' in f
            ],
            'filter-options': [
                Output(f['layout']['id'], 'options')
                for f in FILTERS if 'filter' in f and filters_reg[f['filter']['name']].HAS_OPTIONS
            ]
        },
        inputs_config={
            'buttons': [
                Input(x, 'n_clicks')
                for x in [
                    'input-mkt-clear',
                    'input-strategy-clear',
                    'btn-cache-clear',
                    'btn-db-refresh',
                    'btn-db-upload',
                    'btn-db-reconnect',
                    'btn-strategy-run',
                    'btn-strategy-download'
                ]
            ],
            'sorter': Input('market-sorter', 'value'),
            'filter-inputs': {
                f['filter']['kwargs']['db_col']: Input(f['layout']['id'], 'value')
                for f in FILTERS if 'filter' in f
            }
        },
        states_config={
            'strategy-run': State('input-strategy-run', 'value'),
            'strategy-cell': State('table-strategies', 'active_cell'),
            'strategy-id': State('selected-strategy', 'data')
        },
        process=market_callback
    )

    # @app.callback(
    #     output=[
    #         Output('market-query-status', 'children'),
    #         Output('table-market-session', 'data'),
    #         Output('table-market-session', "selected_cells"),
    #         Output('table-market-session', 'active_cell'),
    #         Output('table-market-session', 'page_current'),
    #         Output('loading-out-session', 'children'),
    #         Output('intermediary-session-market', 'children'),
    #         Output('notifications-market', 'data'),
    #
    #         Output('input-sport-type', 'value'),
    #         Output('input-mkt-type', 'value'),
    #         Output('input-bet-type', 'value'),
    #         Output('input-format', 'value'),
    #         Output('input-country-code', 'value'),
    #         Output('input-venue', 'value'),
    #         Output('input-date', 'value'),
    #         Output('input-mkt-id', 'value'),
    #
    #         Output('input-sport-type', 'options'),
    #         Output('input-mkt-type', 'options'),
    #         Output('input-bet-type', 'options'),
    #         Output('input-format', 'options'),
    #         Output('input-country-code', 'options'),
    #         Output('input-venue', 'options'),
    #         Output('input-date', 'options')
    #     ],
    #     inputs=[
    #         Input('input-mkt-clear', 'n_clicks'),
    #         Input('input-strategy-clear', 'n_clicks'),
    #         Input('btn-cache-clear', 'n_clicks'),
    #         Input('btn-db-refresh', 'n_clicks'),
    #         Input('btn-db-upload', 'n_clicks'),
    #         Input('btn-db-reconnect', 'n_clicks'),
    #         Input('btn-strategy-run', 'n_clicks'),
    #         Input('market-sorter', 'value'),
    #         Input('btn-strategy-download', 'n_clicks'),
    #
    #         Input('input-sport-type', 'value'),
    #         Input('input-mkt-type', 'value'),
    #         Input('input-bet-type', 'value'),
    #         Input('input-format', 'value'),
    #         Input('input-country-code', 'value'),
    #         Input('input-venue', 'value'),
    #         Input('input-date', 'value'),
    #         Input('input-mkt-id', 'value')
    #     ],
    #     state=[
    #         State('input-strategy-run', 'value'),
    #         State('table-strategies', 'active_cell')
    #     ]
    # )
    # def mkt_intermediary(
    #         n_mkt_clear,
    #         n_strat_clear,
    #         n_cache_clear,
    #         n_db_refresh,
    #         n_db_upload,
    #         n_db_reconnect,
    #         n_strat_run,
    #         market_sorter,
    #         n_strat_download,
    #         m0, m1, m2, m3, m4, m5, m6, m7,
    #         strategy_run_val,
    #         strategy_tbl_cell,
    # ):
    #     flt_market_args = [m0, m1, m2, m3, m4, m5, m6, m7]
    #     btn_id = dashutils.triggered_id()
    #     notifs = []
    #     post_notification(notifs, 'info',  'Market Database', 'Updated markets')
    #
    #     # run new strategy if requested
    #     if btn_id == 'btn-strategy-run':
    #         shn.strat_update()  # update configurations first
    #         if strategy_run_val is None:
    #             post_notification(notifs, 'warning', 'Strategy', 'cannot run strategy without selecting one')
    #         else:
    #             strategy_id = str(shn.strat_run(strategy_run_val))
    #             post_notification(notifs, 'info', 'Strategy',  f'created new strategy "{strategy_id}"')
    #             shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits)  # upload strategy from cache
    #
    #     # wipe cache if requested
    #     if btn_id == 'btn-cache-clear':
    #         n_files, n_dirs = shn.betting_db.wipe_cache()
    #         post_notification(notifs, 'info', 'Cache', f'Cleared {n_files} files and {n_dirs} dirs from cache')
    #
    #     # TODO - move all strategy functions from here to strategy page
    #     # reconnect to database if button pressed
    #     if btn_id == 'btn-db-reconnect':
    #         shn.rl_db()
    #         post_notification(notifs, 'info', 'Database', 'reconnected to database')
    #
    #     # upload market & strategy cache if "upload" button clicked
    #     if btn_id == 'btn-db-upload':
    #         n_mkt = len(shn.betting_db.scan_mkt_cache())
    #         n_strat = len(shn.betting_db.scan_strat_cache(tt.TradeTracker.get_runner_profits))
    #         post_notification(notifs, 'info', 'Cache', f'found {n_mkt} new markets in cache')
    #         post_notification(notifs, 'info', 'Cache', f'found {n_strat} new strategies in cache')
    #
    #     # update strategy filters and selectable options
    #     if btn_id == 'btn-strategy-download':
    #         if 'row_id' not in strategy_tbl_cell:
    #             post_notification(notifs, 'warning', 'Strategy', 'no row ID found in strategy cell')
    #             shn.active_strat_set(None)
    #         else:
    #             shn.active_strat_set(strategy_tbl_cell['row_id'])
    #
    #     # clear strategy ID variable used in market filtering if "clear strategy" button clicked
    #     if btn_id in ['input-strategy-clear', 'btn-db-reconnect', 'btn-strategy-delete']:
    #         shn.active_strat_set(None)
    #
    #
    #     # update market filters and selectable options
    #     mkt_clear = btn_id in ['input-mkt-clear', 'btn-db-reconnect']
    #     flt_market_args = [None if mkt_clear else v for v in flt_market_args]
    #     shn.betting_db.meta_de_serialise()
    #     column_filters = shn.market_filter_conditions(flt_market_args)
    #
    #     # shn.filters_mkt.update_filters(clear=mkt_clear, args=flt_market_args)
    #
    #     cte = shn.betting_db.filters_mkt_cte(shn.active_strat_get(), column_filters)
    #     vals = shn._flts_mkt
    #     # vals = shn.filters_mkt.filters_values()
    #     lbls = shn.betting_db.filters_labels(shn.filters_mkt, cte)
    #     if btn_id == 'btn-sort-clear':
    #         market_sorter = None
    #     if market_sorter:
    #         dropdown_dict = json.loads(market_sorter)
    #         order_col = dropdown_dict.get('db_col')
    #         order_asc = dropdown_dict.get('asc')
    #     else:
    #         order_col, order_asc = None, None
    #
    #     # query db with filtered CTE to generate table rows for display
    #     tbl_rows = shn.mkt_tbl_rows(cte, order_col, order_asc)
    #
    #     # assign 'id' so market ID set in row ID read in callbacks
    #     for r in tbl_rows:
    #         r['id'] = r['market_id']
    #
    #     # generate status string of markets/strategies available and strategy selected
    #     n = shn.betting_db.cte_count(cte)
    #     ns = shn.betting_db.strategy_count()
    #     q_sts = [
    #         html.Div(f'Showing {len(tbl_rows)} of {n} available, {ns} strategies available'),
    #         html.Div(
    #             f'strategy ID: {shn.active_strat_get()}'
    #             if shn.active_strat_get() is not None else 'No strategy selected'
    #         )
    #     ]
    #
    #     # combine all outputs together
    #     return [
    #         q_sts,  # table query status
    #         tbl_rows,  # set market table row data
    #         [],  # clear selected cell(s)
    #         None,  # clear selected cell
    #         0,  # reset current page back to first page
    #         '',  # loading output
    #         counter.next(),  # intermediary counter value
    #         notifs,
    #         # market_sorter  # market sorter value
    #     ] + vals + lbls

    @app.callback(
        [
            Output('input-strategy-run', 'options'),
            Output('intermediary-strat-reload', 'children'),
            Output('notifications-strategy-reload', 'data'),
        ],
        Input('btn-strategies-reload', 'n_clicks')
    )
    def strategy_run_reload(n_reload):
        n_confs = len(shn.strat_update())
        notifs = []
        post_notification(notifs, 'info', 'Strategy Configs', f'loaded {n_confs} strategy configs')

        options = [{
            'label': v,
            'value': v
        } for v in shn.strat_cfg_names]

        return [
            options,
            strat_counter.next(),
            notifs
        ]

    @app.callback(
        Output('btn-strategy-run', 'disabled'),
        Input('input-strategy-run', 'value')
    )
    def strategy_run_enable(strategy_run_select):
        return strategy_run_select is None



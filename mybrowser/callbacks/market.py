from dash.dependencies import Output, Input, State
import dash_html_components as html

import myutils.mydash
import logging
from ..session import Session

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = myutils.mydash.Intermediary()


def cb_market(app, shn: Session):
    @app.callback(
        output=[
            Output('input-strategy-select', 'value'),
            Output('input-strategy-select', 'options'),
        ],
        inputs=[
            Input('input-strategy-clear', 'n_clicks'),
            Input('input-strategy-select', 'value'),
        ],
    )
    def strategy_callback(n_clicks, *flt_args):
        clear = myutils.mydash.triggered_id() == 'input-strategy-clear'

        shn.flt_upsrt(clear, *flt_args)
        cte = shn.flt_ctesrt()

        vals = shn.flt_valssrt()
        opts = shn.flt_optssrt(cte)
        return vals + opts

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

            Output('input-sport-type', 'options'),
            Output('input-mkt-type', 'options'),
            Output('input-bet-type', 'options'),
            Output('input-format', 'options'),
            Output('input-country-code', 'options'),
            Output('input-venue', 'options'),
            Output('input-date', 'options'),
        ],
        inputs=[
            Input('input-mkt-clear', 'n_clicks'),
            Input('table-market-session', 'sort_mode'),
            Input('input-strategy-select', 'value'),
            Input('btn-db-refresh', 'n_clicks'),

            Input('input-sport-type', 'value'),
            Input('input-mkt-type', 'value'),
            Input('input-bet-type', 'value'),
            Input('input-format', 'value'),
            Input('input-country-code', 'value'),
            Input('input-venue', 'value'),
            Input('input-date', 'value'),
        ],
        states=[
            State('table-market-session', 'active_cell')
        ]
    )
    def mkt_intermediary(
            n_clicks,
            sort_mode,
            strategy_id,
            refresh,
            *args
    ):
        clear = myutils.mydash.triggered_id() == 'input-mkt-clear'

        shn.flt_upmkt(clear, *args)
        cte = shn.flt_ctemkt(strategy_id)
        tbl_rows = shn.flt_tbl(cte)
        for r in tbl_rows:
            r['id'] = r['market_id']  # assign 'id' so market ID set in row ID read in callbacks
        vals = shn.flt_valsmkt()
        opts = shn.flt_optsmkt(cte)
        n = shn.betting_db.session.query(cte).count()
        ns = shn.betting_db.session.query(shn.betting_db.tables['strategymeta']).count()

        q_sts = [
            html.Div(f'Showing {len(tbl_rows)} of {n} available, {ns} strategies available'),
            html.Div(
                f'strategy ID={strategy_id}'
                if strategy_id is not None else 'no strategy selected'
            )
        ]

        return [
            q_sts,  # table query status
            tbl_rows,  # set market table row data
            [],  # clear selected cell(s)
            None,  # clear selected cell
            0,  # reset current page back to first page
            '',  # loading output
            counter.next()  # intermediary counter value
        ] + vals + opts

    @app.callback(
        Output("right-side-bar", "className"),
        [
            Input("btn-session-filter", "n_clicks"),
            Input("btn-right-close", "n_clicks")
        ],
    )
    def toggle_classname(n1, n2):
        if myutils.mydash.triggered_id() == 'btn-session-filter':
            return "right-not-collapsed"
        else:
            return ""

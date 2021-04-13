from dash.dependencies import Output, Input, State
from myutils.mydash import intermediate
from myutils.mydash import context
import logging
from ..session import Session

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = intermediate.Intermediary()


def cb_market(app, shn: Session):

    # TODO - expand strategy select inputs
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
        clear = context.triggered_id() == 'input-strategy-clear'

        shn.flt_upsrt(clear, *flt_args)
        cte = shn.flt_ctesrt()

        vals = shn.flt_valssrt()
        opts = shn.flt_optssrt(cte)
        return vals + opts

    # TODO - split date into year/month/day components
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
            *args
    ):
        clear = context.triggered_id() == 'input-mkt-clear'

        shn.flt_upmkt(clear, *args)
        cte = shn.flt_ctemkt(strategy_id)
        tbl_rows = shn.flt_tbl(cte)
        for r in tbl_rows:
            r['id'] = r['market_id']  # assign 'id' so market ID set in row ID read in callbacks
        vals = shn.flt_valsmkt()
        opts = shn.flt_optsmkt(cte)
        n = shn.betting_db.session.query(cte).count()

        return [
            f'Showing {len(tbl_rows)} of {n} available',  # table query status
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
        if context.triggered_id() == 'btn-session-filter':
            return "right-not-collapsed"
        else:
            return ""

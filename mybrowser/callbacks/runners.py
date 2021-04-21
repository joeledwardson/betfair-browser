from dash.dependencies import Output, Input, State
import dash_html_components as html
import logging
from ..session import Session
from myutils.mydash import intermediate
from myutils.mydash import context


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = intermediate.Intermediary()


def cb_runners(app, shn: Session):
    @app.callback(
        output=Output('button-runners', 'disabled'),
        inputs=[
            Input('table-market-session', 'active_cell'),
        ],
    )
    def btn_disable(active_cell):
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
            Output('button-mkt-bin', 'disabled'),
            Output('button-all-figures', 'disabled'),
            Output('table-runners', 'active_cell'),
            Output('table-runners', 'selected_cells'),
            Output('loading-out-runners', 'children'),
        ],
        inputs=[
            Input('button-runners', 'n_clicks'),
            Input('button-mkt-bin', 'n_clicks')
        ],
        state=[
            State('table-market-session', 'active_cell'),
            State('input-strategy-select', 'value')
        ],
    )
    def runners_pressed(btn_rn, btn_clr, cell, strategy_id):
        """
        update runners table and market information table, based on when "get runners" button is clicked
        update data in runners table, and active file indicator when runners button pressed

        :param btn_rn:
        :param active_cell:
        :return:
        """

        ret = [
            [],  # empty table
            html.P('no market selected'),  # market status
            counter.next(),  # intermediary value increment
            True,  # by default assume market not loaded, bin market button disabled
            True,  # by default assume market not loaded, figures button disabled
            None,  # reset active cell
            [],  # reset selected cells
            ''  # blank loading output
        ]

        # assume market not loaded, clear
        shn.mkt_clr()

        # first callback call
        if not btn_rn:
            return ret

        # market clear
        if context.triggered_id() == 'button-mkt-bin':
            active_logger.info(f'clearing market')
            return ret

        if not cell:
            active_logger.warning(f'no active cell to get market')
            return ret

        market_id = cell['row_id']
        if not market_id:
            active_logger.warning(f'row ID is blank')
            return ret

        if not shn.mkt_load(market_id, strategy_id):
            shn.mkt_clr()
            return ret
        shn.mkt_lginf()

        tbl = [{
            'id': d['runner_id'],  # set row to ID for easy access in callbacks
            'Selection ID': d['runner_id'],
            'Name': d['runner_name'],
            'Starting Odds':  d['start_odds'],
            'Profit': d['runner_profit']
        } for d in shn.mkt_rnrs.values()]

        ret[0] = sorted(tbl, key=lambda d: d['Starting Odds'])
        ret[1] = f'loaded "{market_id}"'
        ret[3] = False  # enable bin market button
        ret[4] = False  # enable plot all figures button
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
        output=[
            Output('button-figure', 'disabled'),
            Output('button-orders', 'disabled')
        ], inputs=[
            Input('table-runners', 'active_cell')
        ]
    )
    def fig_btn_disable(active_cell):
        active_logger.info(f'runners button callback, runners cell: {active_cell}')
        dsbl_fig = True
        dsbl_odr = True

        if active_cell is not None and 'row_id' in active_cell:
            dsbl_fig = False
            if shn.mkt_sid is not None:
                dsbl_odr = False

        return dsbl_fig, dsbl_odr


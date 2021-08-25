from dash.dependencies import Output, Input, State
import dash_html_components as html
import logging
import traceback
from typing import List

from myutils import dashutils
from mytrading import exceptions as trdexp
from sqlalchemy.exc import SQLAlchemyError
from ..session import Session, LoadedMarket, post_notification


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = dashutils.Intermediary()


def cb_runners(app, shn: Session):
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
            Output('selected-market', 'data'),
            Output('notifications-runners', 'data')
        ],
        inputs=[
            Input('button-runners', 'n_clicks'),
            Input('button-mkt-bin', 'n_clicks')
        ],
        state=[
            State('table-market-session', 'active_cell'),
        ],
    )
    def runners_pressed(btn_rn, btn_clr, cell):
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
            '',  # blank loading output
            {}, # blank selected market
            [], # no notifications
        ]
        notifs = ret[-1]

        # assume market not loaded, clear
        # shn.mkt_clr()

        # first callback call
        if not btn_rn:
            return ret

        # market clear
        if dashutils.triggered_id() == 'button-mkt-bin':
            active_logger.info(f'clearing market')
            post_notification(notifs, "info", 'Market', 'Cleared market')
            return ret

        if not cell:
            active_logger.warning(f'no active cell to get market')
            post_notification(notifs, "warning", 'Market', 'No active cell to get market')
            return ret

        market_id = cell['row_id']
        if not market_id:
            active_logger.warning(f'row ID is blank')
            post_notification(notifs, "warning", 'Market', 'row ID is blank')
            return ret
        try:
            loaded_market = shn.mkt_load(market_id, shn.active_strat_get())
            shn.mkt_lginf(loaded_market)
            info_str = f'Loaded market "{market_id}" with strategy "{shn.active_strat_get()}"'
            post_notification(notifs, "info", 'Market', info_str)
        except (trdexp.MyTradingException, SQLAlchemyError) as e:
            active_logger.warning(f'failed to load market: {e}\n{traceback.format_exc()}')
            return ret

        tbl = [d | {
            'id': d['runner_id'],  # set row to ID for easy access in callbacks
        } for d in loaded_market['runners'].values()]

        # serialise market info
        shn.betting_db.meta_serialise(loaded_market['info'])

        ret[0] = sorted(tbl, key=lambda d: d['starting_odds'])
        ret[1] = f'loaded "{market_id}"'
        ret[3] = False  # enable bin market button
        ret[4] = False  # enable plot all figures button
        ret[8] = loaded_market
        return ret

    @app.callback(
        Output("container-filters-plot", "className"),
        [
            Input("btn-runners-filter", "n_clicks"),
            Input("btn-plot-close", "n_clicks")
        ],
        State("container-filters-plot", "className")
    )
    def toggle_classname(n1, n2, css_classes):
        if dashutils.triggered_id() == 'btn-runners-filter':
            return str(dashutils.CSSClassHandler(css_classes) + 'right-not-collapsed')
        else:
            return str(dashutils.CSSClassHandler(css_classes) - 'right-not-collapsed')

    @app.callback(
        [
            Output('button-figure', 'disabled'),
            Output('button-orders', 'disabled')
        ], [
            Input('table-runners', 'active_cell')
        ], [
            State('selected-market', 'data')
        ]
    )
    def fig_btn_disable(active_cell, loaded_market: LoadedMarket):
        active_logger.info(f'runners button callback, runners cell: {active_cell}')
        disable_figure = True
        disable_orders = True

        if active_cell is not None and 'row_id' in active_cell:
            disable_figure = False
            if loaded_market['strategy_id'] is not None:
                disable_orders = False

        return disable_figure, disable_orders


from dash.dependencies import Output, Input, State
import logging
import traceback

import myutils.dashutils
from ..session import Session, LoadedMarket
from ..exceptions import SessionException

active_logger = logging.getLogger(__name__)
counter = myutils.dashutils.Intermediary()


def cb_orders(app, shn: Session):
    @app.callback(
        output=[
            Output('table-orders', 'data'),
            Output('table-orders', 'page_current'),
            Output('intermediary-orders', 'children'),
        ],
        inputs=[
            Input('button-orders', 'n_clicks'),
            Input('button-runners', 'n_clicks'),
        ],
        state=[
            State('table-runners', 'active_cell'),
            State('selected-market', 'data'),
            State('selected-strategy', 'data'),
        ]
    )
    def update_orders_table(n1, n2, cell, selected_market: LoadedMarket, strategy_id):
        orders_pressed = myutils.dashutils.triggered_id() == 'button-orders'
        r = [
            list(),
            0,  # reset selected page on open/close modal - if last page selected was page 2 and new table loaded is
            # only 1 page then table breaks
            counter.next()
        ]
        active_logger.info(f'attempting to get orders, active cell: {cell}')

        # if runners button pressed (new active market), clear table
        if not orders_pressed:
            return r

        # if no active market selected then abort
        if not selected_market:
            active_logger.warning('no market information')
            return r

        # get selection ID of runner from active runner cell, on fail clear table
        if not cell:
            active_logger.warning('no cell selected')
            return r

        if 'row_id' not in cell:
            active_logger.warning(f'row ID not found in active cell info')
            return r

        selection_id = cell['row_id']
        shn.deserialise_loaded_market(selected_market)
        if selection_id not in selected_market['runners']:
            active_logger.warning(f'row ID "{selection_id}" not found in starting odds')
            return r

        if not strategy_id:
            active_logger.warning(f'no strategy selected')
            return r

        try:
            df = shn.odr_prft(selection_id, selected_market, strategy_id)
        except SessionException as e:
            active_logger.warning(f'getting order profits failed: {e}\n{traceback.format_exc()}')
            return r

        active_logger.info(f'producing orders for {selection_id}, {df.shape[0]} results found"')
        r[0] = df.to_dict('records')
        # r[1] = True
        return r

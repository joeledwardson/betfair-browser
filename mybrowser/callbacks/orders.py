from dash.dependencies import Output, Input, State
import logging
import traceback

import myutils.mydash
from ..session import Session, SessionException


active_logger = logging.getLogger(__name__)
counter = myutils.mydash.Intermediary()


def cb_orders(app, shn: Session):
    @app.callback(
        output=[
            Output('table-orders', 'data'),
            Output('modal-orders', 'is_open'),
            Output('table-orders', 'page_current'),
            Output('intermediary-orders', 'children'),
        ],
        inputs=[
            Input('button-orders', 'n_clicks'),
            Input('button-runners', 'n_clicks'),
            Input('modal-close-orders', 'n_clicks')
        ],
        state=[
            State('table-runners', 'active_cell'),
        ]
    )
    def update_orders_table(n1, n2, n3, cell):

        orders_pressed = myutils.mydash.triggered_id() == 'button-orders'
        r = [
            list(),
            False,
            0,  # reset selected page on open/close modal - if last page selected was page 2 and new table loaded is
            # only 1 page then table breaks
            counter.next()
        ]
        if myutils.mydash.triggered_id() == 'modal-close-orders':
            return r

        active_logger.info(f'attempting to get orders, active cell: {cell}')

        # if runners button pressed (new active market), clear table
        if not orders_pressed:
            return r

        # if no active market selected then abort
        if not shn.mkt_records or not shn.mkt_info:
            active_logger.warning('no market information/records')
            return r

        # get selection ID of runner from active runner cell, on fail clear table
        if not cell:
            active_logger.warning('no cell selected')
            return r

        if 'row_id' not in cell:
            active_logger.warning(f'row ID not found in active cell info')
            return r

        selection_id = cell['row_id']
        if selection_id not in shn.mkt_rnrs:
            active_logger.warning(f'row ID "{selection_id}" not found in starting odds')
            return r

        if not shn.mkt_sid:
            active_logger.warning(f'no strategy selected')
            return r

        try:
            df = shn.odr_prft(selection_id)
        except SessionException as e:
            active_logger.warning(f'getting order profits failed: {e}\n{traceback.format_exc()}')
            return r

        active_logger.info(f'producing orders for {selection_id}, {df.shape[0]} results found"')
        r[0] = df.to_dict('records')
        r[1] = True
        return r

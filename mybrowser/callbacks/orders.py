from dash.dependencies import Output, Input, State
import logging
import traceback
from typing import List
from myutils.dashutils import Config, TDict, dict_callback, triggered_id
from ..session import Session, LoadedMarket, post_notification, Notification
from ..exceptions import SessionException

active_logger = logging.getLogger(__name__)


def cb_orders(app, shn: Session):
    @dict_callback(
        app=app,
        outputs_config={
            'table': Output('table-orders', 'data'),
            'page': Output('table-orders', 'page_current'),
            'notifications': Output('notifications-orders', 'data')
        },
        inputs_config={
            'buttons': [
                Input('button-orders', 'n_clicks'),
                Input('button-runners', 'n_clicks'),
            ]
        },
        states_config={
            'cell': State('table-runners', 'active_cell'),
            'loaded-market': State('selected-market', 'data'),
            'strategy-id': State('selected-strategy', 'data'),
        }
    )
    def orders_callback(outputs: TDict, inputs: TDict, states: TDict):
        outputs['table'] = []
        outputs['page'] = 0 # reset selected page on new table - if last page selected was page 2 and new table
        # loaded is only 1 page then table breaks

        notifs = outputs['notifications'] = []
        orders_pressed = triggered_id() == 'button-orders'
        # if runners button pressed (new active market), clear table
        if not orders_pressed:
            return

        # if no active market selected then abort
        selected_market = states['loaded-market']
        if not selected_market:
            post_notification(notifs, 'warning', 'Orders', 'no market information to get orders')
            return

        # get selection ID of runner from active runner cell, on fail clear table
        if not states['cell']:
            post_notification(notifs, 'warning', 'Orders', 'no cell selected to get runner orders')
            return

        if 'row_id' not in states['cell']:
            post_notification(notifs, 'warning', 'Orders', f'row ID not found in active cell info')
            return

        selection_id = states['cell']['row_id']
        shn.deserialise_loaded_market(selected_market)
        if selection_id not in selected_market['runners']:
            post_notification(notifs, 'warning', 'Orders', f'row ID "{selection_id}" not found in starting odds')
            return

        strategy_id = states['strategy-id']
        if not strategy_id:
            post_notification(notifs, 'warning', 'Orders', 'no strategy selected')
            return

        try:
            df = shn.odr_prft(selection_id, selected_market, strategy_id)
        except SessionException as e:
            msg = f'getting order profits failed: {e}\n{traceback.format_exc()}'
            post_notification(notifs, 'warning', 'Orders', msg)
            return

        if not df.shape[0]:
            post_notification(notifs, 'warning', 'Orders', f'no orders found for runner "{selection_id}"')
            return

        post_notification(notifs, 'info', 'Orders', f'Got {df.shape[0]} orders for runner "{selection_id}"')
        outputs['table'] = df.to_dict('records')
        outputs['notifications'] = notifs

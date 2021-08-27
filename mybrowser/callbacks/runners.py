from dash.dependencies import Output, Input, State
import dash_html_components as html
import logging
import traceback
from typing import List

from myutils import dashutils
from myutils.dashutils import Config, TDict, dict_callback, triggered_id
from mytrading import exceptions as trdexp
from sqlalchemy.exc import SQLAlchemyError
from ..session import Session, LoadedMarket, post_notification
from ..error_catcher import exceptions

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def cb_runners(app, shn: Session):
    @dashutils.dict_callback(
        app=app,
        outputs_config={
            'table': Output('table-runners', 'data'),
            'info': Output('infobox-market', 'children'),
            'disable-bin': Output('button-mkt-bin', 'disabled'),
            'disable-figures': Output('button-all-figures', 'disabled'),
            'cell':  Output('table-runners', 'active_cell'),
            'cells': Output('table-runners', 'selected_cells'),
            'loading': Output('loading-out-runners', 'children'),
            'selected-market': Output('selected-market', 'data'),
            'notifications': Output('notifications-runners', 'data')
        },
        inputs_config={
            'buttons': [
                Input('button-runners', 'n_clicks'),
                Input('button-mkt-bin', 'n_clicks')
            ]
        },
        states_config={
            'cell': State('table-market-session', 'active_cell'),
            'strategy-id': State('selected-strategy', 'data')
        }
    )
    def orders_callback(outputs: TDict, inputs: TDict, states: TDict):
        """
        update runners table and market information table, based on when "get runners" button is clicked
        update data in runners table, and active file indicator when runners button pressed

        :param btn_rn:
        :param active_cell:
        :return:
        """
        outputs['table'] = []  # empty table
        outputs['info'] = html.P('no market selected'),  # market status
        outputs['disable-bin'] = True,  # by default assume market not loaded, bin market button disabled
        outputs['disable-figures'] = True # by default assume market not loaded, figures button disabled
        outputs['cell'] = None  # reset active cell
        outputs['cells'] = []  # reset selected cells
        outputs['loading'] = ''  # blank loading output
        outputs['selected-market'] = {}  # blank selected market by default
        notifs = outputs['notifications'] = []

        # check for first callback call
        if triggered_id() not in ['button-runners', 'button-mkt-bin']:
            return

        # market clear
        if triggered_id() == 'button-mkt-bin':
            post_notification(notifs, "info", 'Market', 'Cleared market')
            return

        cell = states['cell']
        if not cell:
            post_notification(notifs, "warning", 'Market', 'No active cell to get market')
            return

        market_id = cell['row_id']
        if not market_id:
            post_notification(notifs, "warning", 'Market', 'row ID from cell is blank')
            return

        strategy_id = states['strategy-id']
        try:
            loaded_market = shn.mkt_load(market_id, strategy_id)
            shn.mkt_lginf(loaded_market)
            info_str = f'Loaded market "{market_id}" with strategy "{strategy_id}"'
            post_notification(notifs, "info", 'Market', info_str)
        except exceptions as e:
            post_notification(notifs, 'warning', 'Market', f'failed to load market: {e}\n{traceback.format_exc()}')
            return

        tbl = [d | {
            'id': d['runner_id'],  # set row to ID for easy access in callbacks
        } for d in loaded_market['runners'].values()]

        # serialise market info
        shn.serialise_loaded_market(loaded_market)

        outputs['table'] = sorted(tbl, key=lambda d: d['starting_odds'])
        outputs['info'] = f'loaded "{market_id}"'
        outputs['disable-bin'] = False  # enable bin market button
        outputs['disable-figures'] = False  # enable plot all figures button
        outputs['selected-market'] = loaded_market
        return

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


from flumine import FlumineBacktest, clients, BaseStrategy
from flumine.order.order import BaseOrder, BetfairOrder, OrderStatus
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue

import json
import logging
from myutils import betting, bf_feature, bf_window, statemachine as stm, bf_utils as bfu
from myutils.bf_types import MatchBetSums, get_match_bet_sums
from myutils import json_file
from typing import List, Dict
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from uuid import UUID
import pandas as pd

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def get_trade_data(file_path) -> pd.DataFrame:
    """get `TradeTracker` data written to file in dataframe format, if fail, return None"""
    if file_path:
        order_data = json_file.read_file(file_path)
        if order_data:
            order_df = pd.DataFrame(order_data)
            order_df.index = [datetime.fromtimestamp(x) for x in order_df['dt']]
            return order_df.drop(['dt'], axis=1)
    return None


@dataclass
class OrderTracker:
    """track the status and matched money of an order"""
    matched: float
    status: OrderStatus


def serializable_order_info(order: BetfairOrder) -> dict:
    """convert betfair order to JSON serializable format"""

    # copy order info so modifications don't change original object
    info = order.info.copy()

    # convert trade ID to string
    info['trade']['id'] = str(info['trade']['id'])

    # convert strategy object in trade to dict of info
    info['trade']['strategy'] = info['trade']['strategy'].info

    # convert strategy status to string
    info['trade']['status'] = str(info['trade']['status'])

    # add runner status to order
    info['runner_status'] = str(order.runner_status)

    return info


def order_profit(order_info: dict) -> float:
    """
    Compute order profit from dictionary of values retrieved from a line of a file written to by TradeTracker.log_update

    Function is shamelessly stolen from `flumine.backtest.simulated.Simulated.profit`, but that requires an order
    instance which is not possible to create trade/strategy information etc
    """

    sts = order_info['runner_status']
    side = order_info['info']['side']
    price = order_info['info']['average_price_matched']
    size = order_info['info']['size_matched']

    if sts == "WINNER":
        if side == "BACK":
            return round((price - 1) * size, ndigits=2)
        else:
            return round((price - 1) * -size, ndigits=2)
    elif sts == "LOSER":
        if side == "BACK":
            return -size
        else:
            return size
    else:
        return 0.0


@dataclass
class TradeTracker:
    """
    Track trades for a runner, logging order updates

    List of trades kept for all trades on a chosen runner (by `selection_id`) in one market. Active trade denoted by
    `active_trade` (assumes that only 1 trade is happening on a runner at any given time)
    Similarly, active order on active trade denoted by `active_order`

    `open_side` indicates the side of the open order for the current trade

    if `file_path` is specified, it is used as the path to log updates to as well as logging to stream
    """

    selection_id: int
    trades: List[Trade] = field(default_factory=list)
    active_trade: Trade = field(default=None)
    active_order: BetfairOrder = field(default=None)
    open_side: str = field(default=None)

    _log: List[Dict] = field(default_factory=list)
    file_path: str = field(default=None)

    # indexed by trade ID -> order ID
    order_tracker: Dict[UUID, Dict[UUID, OrderTracker]] = field(default_factory=dict)

    def update_order_tracker(self, publish_time: datetime):
        """
        loop orders in each trade instance, and log update message where order amount matched or status has changed
        since last call of function
        """
        ot = self.order_tracker
        for trade in self.trades:
            if trade.id not in ot:
                self.log_update(
                    f'started tracking trade "{trade.id}"',
                    publish_time,
                    to_file=False
                )
                ot[trade.id] = dict()
            for order in [o for o in trade.orders if type(o.order_type) == LimitOrder]:
                if order.id not in ot[trade.id]:
                    self.log_update(
                        f'started tracking order "{order.id}"',
                        publish_time,
                        to_file=False
                    )
                    ot[trade.id][order.id] = OrderTracker(
                        matched=order.size_matched,
                        status=order.status)
                else:
                    if order.size_matched != ot[trade.id][order.id].matched:
                        self.log_update(
                            'order side {0} at {1} for £{2:.2f}, now matched £{3:.2f}'.format(
                                order.side,
                                order.order_type.price,
                                order.order_type.size,
                                order.size_matched
                            ),
                            publish_time,
                            order=order,
                        )
                    if order.status != ot[trade.id][order.id].status:
                        self.log_update(
                            'order side {0} at {1} for £{2:.2f}, now status {3}'.format(
                                order.side,
                                order.order_type.price,
                                order.order_type.size,
                                order.status
                            ),
                            publish_time,
                            order=order
                        )
                    ot[trade.id][order.id].status = order.status
                    ot[trade.id][order.id].matched = order.size_matched

    def log_update(
            self,
            msg: str,
            dt: datetime,
            level=logging.INFO,
            to_file=True,
            display_odds: float = 0.0,
            order: BetfairOrder = None,
            trade: Trade = None):
        """
        Log an update
        - msg: verbose string describing the update
        - dt: timestamp in race of update
        - level: log level for stream logging
        - to_file: set to False if update is not to be logged to file as well as stream
        - display_odds: purely visual odds to be used when visualising order updates (actual order odds will be found in
        `order` argument)
        - order: instance of BetfairOrder which will be logged to file
        """

        # print update to stream
        active_logger.log(level, f'{dt} "{self.selection_id}": {msg}')

        # use previous log odds if not given
        if not display_odds and self._log:
            display_odds = self._log[-1]['display_odds']

        # get active trade ID if exists, if trade arg not passed
        if trade:
            trade_id = trade.id
        elif self.active_trade:
            trade_id = self.active_trade.id
        else:
            trade_id = None
        trade_id = str(trade_id)

        # add to internal list
        self._log.append({
            'dt': dt,
            'msg': msg,
            'display_odds': display_odds,
            'order': order,
            'trade_id': trade_id,
        })

        # write to file if path specified
        if self.file_path and to_file:

            # if order instance not given then assume current order
            if not order:
                order = self.active_order

            # get order serialized info (if exist)
            if order:
                order_info = serializable_order_info(order)
            else:
                order_info = None

            json_file.add_to_file(self.file_path, {
                'selection_id': self.selection_id,
                'dt': dt.timestamp(),
                'msg': msg,
                'display_odds': display_odds,
                'order': order_info,
                'trade_id': trade_id,
            })
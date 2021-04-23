from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder

import logging
from enum import Enum

from .messages import MessageTypes, format_message
from .orderinfo import serializable_order_info, write_order_update
from .tradefollower import OrderTracker, TradeFollower
from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass, field
from uuid import UUID

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


# TODO - should this be a dataclass?
# TODO - also shouldn't this have more functions for getting a new trade etc?
# TODO - worth reviewing if cant hack flumine code for trade/order updates
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

    # indexed by trade ID
    _trade_followers: Dict[UUID, TradeFollower] = field(default_factory=dict)
    # cache of tracked orders
    _followed_orders: List[UUID] = field(default_factory=list)

    def update_order_tracker(self, publish_time: datetime):
        """
        loop orders in each trade instance, and log update message where order amount matched or status has changed
        since last call of function
        """
        tfs = self._trade_followers

        # loop trades
        for trade in self.trades:

            # add untracked trades to tracker
            if trade.id not in tfs:
                self.log_update(
                    msg_type=MessageTypes.MSG_TRACK_TRADE,
                    dt=publish_time,
                    msg_attrs={
                        "trade_id": str(trade.id)
                    },
                )
                tfs[trade.id] = TradeFollower()

            # log trade status updates
            tf = tfs[trade.id]
            if tf.status != trade.status:
                self.log_update(
                    msg_type=MessageTypes.MSG_TRADE_UPDATE,
                    dt=publish_time,
                    msg_attrs={
                        'trade_id': str(trade.id),
                        'status': trade.status.value
                    }
                )
            tf.status = trade.status

            # loop limit orders in trade
            for order in [o for o in trade.orders if type(o.order_type) == LimitOrder]:

                # if order untracked, create order tracker and track
                if order.id not in self._followed_orders:
                    self.log_update(
                        msg_type=MessageTypes.MSG_TRACK_ORDER,
                        dt=publish_time,
                        msg_attrs={
                            "order_id": order.id
                        },
                        order=order
                    )
                    tf.order_trackers[order.id] = OrderTracker(
                        matched=order.size_matched,
                        status=order.status
                    )
                    self._followed_orders.append(order.id)
                    continue

                # check if size matched change
                if order.size_matched != tf.order_trackers[order.id].matched:
                    self.log_update(
                        msg_type=MessageTypes.MSG_MATCHED_SIZE,
                        dt=publish_time,
                        msg_attrs={
                            "order_id": order.id,
                            "side": order.side,
                            "price": order.order_type.price,
                            "size": order.order_type.size,
                            "size_matched": order.size_matched
                        },
                        order=order,
                        display_odds=order.order_type.price,
                    )

                # check for status change
                if order.status != tf.order_trackers[order.id].status:

                    msg = ''
                    if order.status == OrderStatus.VIOLATION:
                        msg = order.violation_msg or ''

                    self.log_update(
                        msg_type=MessageTypes.MSG_STATUS_UPDATE,
                        dt=publish_time,
                        msg_attrs={
                            "order_id": order.id,
                            "side": order.side,
                            "price": order.order_type.price,
                            "size": order.order_type.size,
                            "status": order.status.value,
                            'msg': msg,
                        },
                        order=order,
                        display_odds=order.order_type.price,
                    )
                tf.order_trackers[order.id].status = order.status
                tf.order_trackers[order.id].matched = order.size_matched

    def log_update(
            self,
            msg_type: Enum,
            dt: datetime,
            msg_attrs: dict = None,
            level=logging.INFO,
            to_file=True,
            display_odds: float = 0.0,
            order: BetfairOrder = None):
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
        active_logger.log(level, f'{dt} {self.selection_id} {format_message(msg_type.name, msg_attrs)}')

        # use previous log odds if not given
        if not display_odds and self._log:
            display_odds = self._log[-1]['display_odds']

        # if order instance not given then assume current order/trade
        if not order:
            order = self.active_order
            trade = self.active_trade
        else:
            trade = order.trade

        # get trade ID if trade exists else None
        trade_id = trade.id if trade else None

        # add to internal list
        self._log.append({
            'dt': dt,
            'msg_type': msg_type,
            'msg_attrs': msg_attrs,
            'display_odds': display_odds,
            'order': order,
            'trade_id': trade_id,
        })

        # write to file if path specified
        if self.file_path and to_file:

            # get order serialized info (if exist)
            if order:
                order_info = serializable_order_info(order)
            else:
                order_info = None

            # convert message attrs to empty dict if not set
            msg_attrs = msg_attrs or {}

            write_order_update(
                file_path=self.file_path,
                selection_id=self.selection_id,
                dt=dt,
                msg_type=msg_type,
                msg_attrs=msg_attrs,
                display_odds=display_odds,
                order_info=order_info,
                trade_id=trade_id,
            )

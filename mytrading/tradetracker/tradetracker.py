from flumine.order.order import BetfairOrder
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder

import logging
from enum import IntEnum

from .messages import MessageTypes, format_message
from .orderinfo import serializable_order_info, write_order_update
from .ordertracker import OrderTracker
from myutils import jsonfile
from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass, field
from uuid import UUID

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


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
                    msg_type=MessageTypes.TRACK_TRADE,
                    dt=publish_time,
                    msg_attrs={
                        "trade_id": trade.id
                    },
                    to_file=False
                )
                ot[trade.id] = dict()

            for order in [o for o in trade.orders if type(o.order_type) == LimitOrder]:
                if order.id not in ot[trade.id]:
                    self.log_update(
                        msg_type=MessageTypes.TRACK_ORDER,
                        dt=publish_time,
                        msg_attrs={
                            "order_id": order.id
                        },
                        to_file=False
                    )
                    ot[trade.id][order.id] = OrderTracker(
                        matched=order.size_matched,
                        status=order.status
                    )
                    continue

                if order.size_matched != ot[trade.id][order.id].matched:
                    self.log_update(
                        msg_type=MessageTypes.MATCHED_SIZE,
                        dt=publish_time,
                        msg_attrs={
                            "order_id": order.id,
                            "side": order.side,
                            "price": order.order_type.price,
                            "size": order.order_type.size,
                            "size_matched": order.size_matched
                        },
                    )

                if order.status != ot[trade.id][order.id].status:
                    self.log_update(
                        msg_type=MessageTypes.STATUS_UPDATE,
                        dt=publish_time,
                        msg_attrs={
                            "order_id": order.id,
                            "side": order.side,
                            "price": order.order_type.price,
                            "size": order.order_type.size,
                            "status": order.status.value
                        },
                        order=order
                    )
                ot[trade.id][order.id].status = order.status
                ot[trade.id][order.id].matched = order.size_matched

    def log_update(
            self,
            msg_type: IntEnum,
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
        active_logger.log(level, f'{dt} "{format_message(msg_type, msg_attrs)}"')

        # use previous log odds if not given
        if not display_odds and self._log:
            display_odds = self._log[-1]['display_odds']

        # # get active trade ID if exists, if trade arg not passed
        # if trade:
        #     trade_id = trade.id
        # elif self.active_trade:
        #     trade_id = self.active_trade.id
        # else:
        #     trade_id = None
        # trade_id = str(trade_id)

        # add to internal list
        self._log.append({
            'dt': dt,
            'msg_type': msg_type,
            'msg_attrs': msg_attrs,
            'display_odds': display_odds,
            'order': order,
            # 'trade_id': trade_id,
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

            # convert message attrs to empty dict if not set
            msg_attrs = msg_attrs or {}

            write_order_update(
                file_path=self.file_path,
                selection_id=self.selection_id,
                dt=dt,
                msg_type=msg_type,
                msg_attrs=msg_attrs,
                display_odds=display_odds,
                order_info=order_info
            )


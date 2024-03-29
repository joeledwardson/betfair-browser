from __future__ import annotations
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.trade import Trade, TradeStatus
from flumine.order.ordertype import LimitOrder

import logging
from enum import Enum
import pandas as pd
from datetime import datetime
from uuid import UUID
from typing import List, Dict, Optional
from os import path
import json
from dataclasses import dataclass, field

from mytrading.strategy.messages import MessageTypes, format_message
from ..exceptions import TradeTrackerException
from ..process import get_order_profit

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


@dataclass
class OrderTracker:
    """track the status and matched money of an order"""
    matched: float
    status: OrderStatus


@dataclass
class TradeFollower:
    """track the status of a trade"""
    status: TradeStatus = field(default=None)
    order_trackers: Dict[str, OrderTracker] = field(default_factory=dict)


class TradeTracker:
    """
    Track trades for a runner, logging order updates

    List of trades kept for all trades on a chosen runner (by `selection_id`) in one market. Active trade denoted by
    `active_trade` (assumes that only 1 trade is happening on a runner at any given time)
    Similarly, active order on active trade denoted by `active_order`

    `open_side` indicates the side of the open order for the current trade

    if `file_path` is specified, it is used as the path to log updates to as well as logging to stream
    """
    def __init__(self, selection_id: int, strategy, market_id, file_path: Optional[str] = None):
        active_logger.info(f'creating trade tracker with selection ID "{selection_id}" and file path "{file_path}"')
        self.selection_id = selection_id
        self.file_path = file_path

        self._trades: List[Trade] = list()
        self.active_trade: Optional[Trade] = None
        self.active_order: Optional[BetfairOrder] = None
        self.open_side: Optional[str] = None
        self._prv_display_odds = 0
        self._strategy = strategy
        self.market_id = market_id

        # indexed by trade ID
        self._trade_followers: Dict[UUID, TradeFollower] = dict()
        self._followed_orders = list()

    def create_trade(self, handicap):
        trade = Trade(
            market_id=self.market_id,
            selection_id=self.selection_id,
            handicap=handicap,
            strategy=self._strategy
        )
        self._trades.append(trade)
        self._trade_followers[trade.id] = TradeFollower()
        self.active_trade = trade

    @staticmethod
    def serializable_order_info(order: BetfairOrder) -> dict:
        """convert betfair order info to JSON serializable format"""

        # copy order info so modifications don't change original object
        info = order.info.copy()

        # convert trade ID to string
        info['trade']['id'] = str(info['trade']['id'])

        # dont store strategy info
        # convert strategy object in trade to dict of info
        # info['trade']['strategy'] = info['trade']['strategy'].info
        del info['trade']['strategy']

        # convert strategy status to string
        info['trade']['status'] = str(info['trade']['status'])

        # add runner status to order
        info['runner_status'] = str(order.runner_status)

        # add datetime created
        info['date_time_created'] = order.date_time_created.timestamp()
        info['average_price_matched'] = order.average_price_matched

        return info

    @staticmethod
    def get_runner_profits(updates_path: str) -> Dict:
        df = TradeTracker.get_order_updates(updates_path)
        active_logger.info(f'found {df.shape[0]} order updates in file "{updates_path}"')
        if df.shape[0]:
            df = df[df['msg_type'] == MessageTypes.MSG_MARKET_CLOSE.name]
            df['profit'] = [TradeTracker.dict_order_profit(o) for o in df['order_info']]
            return df.groupby(df['selection_id'])['profit'].sum().to_dict()
        else:
            return dict()


    @staticmethod
    def get_orders_from_buffer(buffer: str) -> pd.DataFrame:
        lines = buffer.splitlines()
        try:
            order_data = [json.loads(line) for line in lines]
        except (ValueError, TypeError) as e:
            raise TradeTrackerException(f'Cannot json parse order updates: {e}')

        order_df = pd.DataFrame(order_data)
        if order_df.shape[0]:
            order_df.index = order_df['dt'].apply(datetime.fromtimestamp)
        return order_df

    @staticmethod
    def get_order_updates(file_path: str) -> pd.DataFrame:
        """get `TradeTracker` data written to file in dataframe format, with index set as `pt` converted to datetimes if
        fail, return None"""
        if not path.isfile(file_path):
            raise TradeTrackerException(f'Cannot get order updates, path is not valid file: "{file_path}')

        with open(file_path) as f:
            data = f.read()
            return TradeTracker.get_orders_from_buffer(data)

    @staticmethod
    def dict_order_profit(order_info: dict) -> float:
        """
        Compute order profit from dictionary of values retrieved from a line of a file written to by TradeTracker.log_update

        Function is shamelessly stolen from `flumine.backtest.simulated.Simulated.profit`, but that requires an order
        instance which is not possible to create trade/strategy information etc
        """
        try:
            sts = order_info['runner_status']
            side = order_info['info']['side']
            price = order_info['info']['average_price_matched']
            size = order_info['info']['size_matched']
            return get_order_profit(sts, side, price, size)
        except KeyError as e:
            raise TradeTrackerException(f'failed to get profit elements: {e}')

    def update_order_tracker(self, publish_time: datetime):
        """
        loop orders in each trade instance, and log update message where order amount matched or status has changed
        since last call of function
        """
        tfs = self._trade_followers

        # loop trades
        for trade in self._trades:
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

                # update cached order status and size matched values
                tf.order_trackers[order.id].status = order.status
                tf.order_trackers[order.id].matched = order.size_matched

    def log_close(self, publish_time: datetime):
        for trade in self._trades:
            for order in trade.orders:
                self.log_update(
                    msg_type=MessageTypes.MSG_MARKET_CLOSE,
                    msg_attrs={
                        'runner_status': order.runner_status,
                        'order_id': str(order.id)
                    },
                    dt=publish_time,
                    order=order,
                )

    def log_update(
            self,
            msg_type: Enum,
            dt: datetime,
            msg_attrs: dict = None,
            level=logging.INFO,
            to_file=True,
            display_odds: float = 0.0,
            order: BetfairOrder = None
    ):
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

        # use previous log odds if not given and update
        if not display_odds and self._prv_display_odds:
            display_odds = self._prv_display_odds
        self._prv_display_odds = display_odds

        # if order instance not given then assume current order/trade
        if not order:
            order = self.active_order
            trade = self.active_trade
        else:
            trade = order.trade

        # get trade ID if trade exists else None
        trade_id = trade.id if trade else None

        # write to file if path specified
        if self.file_path and to_file:

            # get order serialized info (if exist)
            if order:
                order_info = self.serializable_order_info(order)
            else:
                order_info = None

            # convert message attrs to empty dict if not set
            msg_attrs = msg_attrs or {}

            data = {
                'selection_id': self.selection_id,
                'dt': dt.timestamp(),
                'msg_type': msg_type.name,
                'msg_attrs': msg_attrs,
                'display_odds': display_odds,
                'order_info': order_info,
                'trade_id': str(trade_id)
            }
            with open(self.file_path, mode='a') as f:
                try:
                    json_data = json.dumps(data)
                except TypeError as e:
                    raise TradeTrackerException(f'failed to serialise data writing to file: "{self.file_path}"\n{e}')
                f.writelines([json_data + '\n'])

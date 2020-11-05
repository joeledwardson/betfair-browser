from datetime import datetime
import pandas as pd
from flumine.order.order import BetfairOrder
import logging
from typing import Dict
from enum import Enum
from myutils.jsonfile import read_file, add_to_file
from ..process.profit import order_profit
from .messages import MessageTypes


active_logger = logging.getLogger(__name__)


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
        return order_profit(sts, side, price, size)
    except Exception as e:
        active_logger.warning(f'failed to get profit elements: "{e}"')
        return 0


def get_order_updates(file_path) -> pd.DataFrame:
    """
    get `TradeTracker` data written to file in dataframe format, if fail, return None
    """
    if file_path:
        order_data = read_file(file_path)
        if order_data:
            order_df = pd.DataFrame(order_data)
            if order_df.shape[0]:
                order_df.index = order_df['dt'].apply(datetime.fromtimestamp)
                return order_df.drop(['dt'], axis=1)
    return pd.DataFrame()


def filter_market_close(orders_df: pd.DataFrame) -> pd.DataFrame:
    """
    filter market close messages from order info dataframe

    Parameters
    ----------
    orders_df :

    Returns
    -------

    """
    if orders_df.shape[0] and 'msg_type' in orders_df.columns:
        return orders_df[orders_df['msg_type'] != MessageTypes.MARKET_CLOSE.name]
    else:
        return orders_df


def serializable_order_info(order: BetfairOrder) -> dict:
    """convert betfair order to JSON serializable format"""

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


def write_order_update(
        file_path: str,
        selection_id: int,
        dt: datetime,
        msg_type: Enum,
        msg_attrs: Dict,
        display_odds: float,
        order_info: Dict,
        trade_id
):
    """
    write an order update to an .orderinfo file

    - 'file_path': specifies the file path to write to
    - 'selection_id': selection ID of the runner
    - 'dt': datetime timestamp in race
    - 'msg_type': identifying message type string
    - 'msg_attrs': dictionary of message attributes
    - 'display_odds': odds to use when displaying on chart
    - 'order_info': flumine/betfair Order oject information in dictionary form
    - 'trade_id': ID of trade, normally can get from 'order_info', but if an order hasn't been placed yet then
    'order_info' is blank
    """

    add_to_file(file_path, {
        'selection_id': selection_id,
        'dt': dt.timestamp(),
        'msg_type': msg_type.name,
        'msg_attrs': msg_attrs,
        'display_odds': display_odds,
        'order_info': order_info,
        'trade_id': str(trade_id)
    })
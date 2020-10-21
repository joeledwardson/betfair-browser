from datetime import datetime
import pandas as pd
from flumine.order.order import BetfairOrder
from myutils import json_file


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


def get_order_updates(file_path) -> pd.DataFrame:
    """
    get `TradeTracker` data written to file in dataframe format, if fail, return None
    """
    if file_path:
        order_data = json_file.read_file(file_path)
        if order_data:
            order_df = pd.DataFrame(order_data)
            order_df.index = order_df['dt'].apply(datetime.fromtimestamp)
            return order_df.drop(['dt'], axis=1)
    return pd.DataFrame()


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

    # add datetime created
    info['date_time_created'] = order.date_time_created
    info['average_price_matched'] = order.average_price_matched

    return info


# def write_order_update(
#         file_path: str,
#         order: BetfairOrder,
#         selection_id: int,
#         dt: datetime,
#         msg: str,
#         display_odds: int,
#         trade_id,
# ):
#
#     # get order serialized info (if exist)
#     if order:
#         order_info = serializable_order_info(order)
#     else:
#         order_info = None
#
#     json_file.add_to_file(file_path, {
#         'selection_id': selection_id,
#         'dt': dt.timestamp(),
#         'msg': msg,
#         'display_odds': display_odds,
#         'order': order_info,
#         'trade_id': trade_id,
#         'dt_created': order.date_time_created.timestamp() if order else None
#     })
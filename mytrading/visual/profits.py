from datetime import datetime

import pandas as pd

from mytrading.tradetracker.orderfile import order_profit
from myutils.generic import dgetattr, dattr_name
from myutils.jsonfile import read_file
from myutils.timing import format_timedelta
from flumine.markets.market import Market
import plotly.graph_objects as go
from myutils.myplotly.table import plotly_table_kwargs

PROFIT_COLUMNS = [
    'date created',
    'trade',
    'side',
    'price',
    'size',
    'average price matched',
    'size matched',
    'trade profit',
    'time to start'
]


# TODO - delete this, really should be read back from files or using same processing function
def _get_profit_df(market: Market) -> pd.DataFrame:


    attrs = [
        'selection_id',
        'date_time_created',
        'trade.id',
        'side',
        'order_type.price',
        'order_type.size',
        'average_price_matched',
        'size_matched',
        'simulated.profit'
    ]

    df = pd.DataFrame([
        {
            a: dgetattr(o, a)
            for a in attrs
        } for o in market.blotter
    ])
    df['trade_profit'] = [sum(
        [o.simulated.profit for o in order.trade.orders]
    ) for order in market.blotter]

    trade_ids = list(df['trade.id'].unique())
    df['trade.id'] = [trade_ids.index(x) for x in df['trade.id'].values]
    df['time_to_start'] = [format_timedelta(market.market_start_datetime - o.publish_time) for o in
                           market.blotter]


    currency_cols = [
        'order_type.size',
        'average_price_matched',
        'size_matched',
        'simulated.profit',
        'trade_profit'
    ]

    def currency_format(x):
        return f'£{x:.2f}'

    for col in currency_cols:
        df[col] = df[col].apply(currency_format)

    df.columns = [dattr_name(a) for a in df.columns]

    return df.sort_values(by=[
        'selection_id',
        'id'
    ])


def get_profit_plotly_table(profit_df: pd.DataFrame, title: str) -> go.Figure:
    # double size of datetime column
    widths = [3 if name == 'date_time_created' else 1 for name in profit_df.columns]

    return go.Figure(
        data=go.Table(
            **plotly_table_kwargs(profit_df),
            columnwidth=widths,
        ),
        layout=dict(
            title=title
        ),
    )


def process_profit_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    - change "date created" to timestamp form
    - turn "trade" column into indexes
    - format currency columns
    - add trade profit and time to start columns
    """
    df.sort_values(by=['date created'])
    df['trade profit'] = df.groupby(['trade'])['simulated profit'].transform('sum')

    trade_ids = list(df['trade'].unique())
    df['trade'] = [trade_ids.index(x) for x in df['trade'].values]

    # df['time_to_start'] = [format_timedelta(market.market_start_datetime - o.publish_time) for o in
    #                        market.blotter]

    currency_cols = [
        'trade profit',
        'simulated profit',
        'size',
        'size matched',
        'average price matched',
    ]

    def currency_format(x):
        return f'£{x:.2f}' if x != 0 else ''

    for col in currency_cols:
        df[col] = df[col].apply(currency_format)

    return df


def read_profit_table(file_path: str) -> pd.DataFrame:
    """
    get table of completed orders and simulated profit from
    """

    # get order results
    lines = read_file(file_path)

    # filter to limit orders
    lines = [order for order in lines if order['order_type']['order_type'] == 'Limit']

    attrs = {
        'date created': 'date_time_created',
        'trade': 'trade.id',
        'side': 'info.side',
        'price': 'order_type.price',
        'size': 'order_type.size',
        'average price matched': 'average_price_matched',
        'size matched': 'info.size_matched'
    }

    df = pd.DataFrame([
        {
            k: dgetattr(o, v, is_dict=True)
            for k, v in attrs.items()
        } for o in lines
    ])
    df['date created'].apply(lambda dt: datetime.fromtimestamp)
    df['simulated profit'] = [order_profit(order) for order in lines]
    return df

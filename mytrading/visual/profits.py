from datetime import datetime

import pandas as pd

from ..strategy.tradetracker.orderinfo import dict_order_profit
from myutils.generic import dgetattr
from myutils.jsonfile import read_file_lines
from myutils.mytiming import format_timedelta
import plotly.graph_objects as go
from myutils.myplotly.table import plotly_table_kwargs

# columns in profit table display
PROFIT_COLUMNS = [
    'date',
    'trade',
    'side',
    'price',
    'size',
    'm-price',
    'matched',
    'order £',
    'trade £',
    't-start'
]


def get_profit_plotly_table(profit_df: pd.DataFrame, title: str) -> go.Figure:
    """
    get plotly figure containing table of profit results from profits dataframe
    """

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

# TODO - needed anymore? - now that order profit has moved to browser getting order profits should be moved here and
#  all code in this file deleted
def process_profit_table(df: pd.DataFrame, market_start_time: datetime) -> pd.DataFrame:
    """
    - change "date" to timestamp form
    - turn "trade" column into indexes
    - format currency columns
    - add trade £ and t-start columns
    """
    # sum order profits in each trade
    df['trade £'] = df.groupby(['trade'])['order £'].transform('sum')

    # convert trade UUIDs to indexes for easy viewing
    trade_ids = list(df['trade'].unique())
    df['trade'] = [trade_ids.index(x) for x in df['trade'].values]

    df['t-start'] = [format_timedelta(market_start_time - dt) for dt in df['date']]

    currency_cols = [
        'trade £',
        'order £',
        'size',
        'matched',
    ]

    def currency_format(x):
        return f'£{x:.2f}' if x != 0 else ''

    for col in currency_cols:
        df[col] = df[col].apply(currency_format)

    # sort earliest first
    return df.sort_values(by=['date'])


def read_profit_table(file_path: str) -> pd.DataFrame:
    """
    get table of completed orders and order £ from
    """

    # get order results
    lines = read_file_lines(file_path)

    # filter to limit orders
    lines = [order for order in lines if order['order_type']['order_type'] == 'Limit']

    attrs = {
        'date': 'date_time_created',
        'trade': 'trade.id',
        'side': 'info.side',
        'price': 'order_type.price',
        'size': 'order_type.size',
        'm-price': 'average_price_matched',
        'matched': 'info.size_matched'
    }

    df = pd.DataFrame([
        {
            k: dgetattr(o, v, is_dict=True)
            for k, v in attrs.items()
        } for o in lines
    ])
    df['date'] = df['date'].apply(datetime.fromtimestamp)
    df['order £'] = [dict_order_profit(order) for order in lines]
    return df

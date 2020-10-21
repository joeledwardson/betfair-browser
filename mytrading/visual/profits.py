import pandas as pd
from myutils.generic import dgetattr, dattr_name
from myutils.timing import format_timedelta
from flumine.markets.market import Market
import plotly.graph_objects as go
from myutils.myplotly.table import plotly_table_kwargs


def get_profit_df(market: Market) -> pd.DataFrame:

    attr = {
        ''
    }

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


def get_profit_table(profit_df: pd.DataFrame, title: str) -> go.Figure:
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
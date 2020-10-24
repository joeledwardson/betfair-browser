import pandas as pd
from plotly import graph_objects as go
import logging
from mytrading.tradetracker.messages import format_message

# must import all strategy message processors
from mytrading.strategies.scalp.messages import WallMessageTypes


active_logger = logging.getLogger(__name__)


def plot_orders(fig: go.Figure, orders_df: pd.DataFrame):
    """
    add dataframe of order information to plot
    """

    # check dataframe not empty
    if orders_df.shape[0] == 0:
        active_logger.warning(f'orders dataframe empty, aborting')
        return

    if 'msg_type' not in orders_df.columns:
        active_logger.warning('"msg_type" not found in orders dataframe, aborting')
        return

    if 'msg_attrs' not in orders_df.columns:
        active_logger.warning('"msg_attrs" not found in orders dataframe, aborting')
        return

    def get_trade_id(order_info):
        if type(order_info) is dict:
            if 'trade' in order_info:
                return order_info['trade']['id']
        return None

    orders_df['trade_id'] = orders_df['order_info'].apply(get_trade_id)

    orders_df['msg'] = orders_df[['msg_type', 'msg_attrs']].apply(
        lambda cols: format_message(cols[0], cols[1]),
        axis=1
    )

    for row in orders_df[orders_df['msg'].isnull()].iterrows():
        active_logger.critical(f'found row with message type "{row[1].get("msg_type")}" has no message!')

    orders_df = orders_df[~orders_df['msg'].isnull()]

    for i, (trade_id, df) in enumerate(orders_df.groupby(['trade_id'])):

        # so can see annotations for overlapping points need to combine text (use last instance for display odds)
        grouped_df = df.groupby(df.index)
        grouped_msg = grouped_df['msg']
        msgs = grouped_msg.apply(lambda x: '<br>'.join(x))
        display_odds = df.groupby(df.index)['display_odds'].last()
        df = pd.concat([msgs, display_odds], axis=1)

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['display_odds'],
            text=df['msg'],
            name='order info',
            legendgroup='order info',
            showlegend=(i == 0),
        ))
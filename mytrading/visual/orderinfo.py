import pandas as pd
from plotly import graph_objects as go
import logging
from mytrading.tradetracker.messages import format_message

# must import all strategy message processors
from mytrading.strategies.scalp.messages import WallMessageTypes
from mytrading.strategies.window.messages import WindowMessageTypes


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

    # replace blank trade ID so they are not ignored by pandas groupby
    orders_df['trade_id'].fillna('-1')

    # use message formatter to convert message type and attributes into single string message
    orders_df['msg'] = orders_df[['msg_type', 'msg_attrs']].apply(
        lambda cols: format_message(cols[0], cols[1]),
        axis=1
    )

    # check for messages equal to None (indicates that message formatter not returning a value)
    for row in orders_df[orders_df['msg'].isnull()].iterrows():
        active_logger.critical(f'found row with message type "{row[1].get("msg_type")}" has no message!')

    # remove null messages
    orders_df = orders_df[~orders_df['msg'].isnull()]

    # convert multi-line message ASCII \n newline characters into HTML newline characters <br>
    orders_df['msg'] = orders_df['msg'].apply(lambda s: '<br>'.join(s.split('\n')))

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
            mode='lines+markers',
            name=f'trade {i}',
            # legendgroup='order info',
            # showlegend=(i == 0),
        ))




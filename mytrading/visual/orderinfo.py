import pandas as pd
from plotly import graph_objects as go
import logging
from ..tradetracker.messages import format_message

# must import all strategy message processors
from ..strategies.scalp.messages import WallMessageTypes
from ..strategies.window.messages import WindowMessageTypes
from ..strategies.trend.messages import TrendMessageTypes
from ..strategies.spike.messages import SpikeMessageTypes


active_logger = logging.getLogger(__name__)

orders_default_config = {
    'trace_args': {},
    'chart_args': {
        'marker_size': 10,
    }
}


def plot_orders(fig: go.Figure, orders_df: pd.DataFrame, display_config=None, show_trade_id=True):
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
    orders_df['trade_id'] = orders_df['trade_id'].fillna('0')

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

    # get default configuration if not passed
    display_config = display_config or orders_default_config

    # loop groups but dont sort
    for i, (trade_id, df) in enumerate(orders_df.groupby(['trade_id'], sort=False)):

        # group dataframe by index (timestamps)
        grouped_df = df.groupby(df.index)

        # combine messages by joining with newline
        msgs = grouped_df['msg'].apply(lambda x: '<br>'.join(x))

        # take last of display odds and trade ID within each timestamp to display
        display_odds = grouped_df['display_odds'].last()
        trade_ids = grouped_df['trade_id'].last()

        # combine messages, display odds and trade ID in dataframe
        df = pd.concat([msgs, display_odds, trade_ids], axis=1)

        # if messages are to contain trade ID, then format trade ID with messages
        if show_trade_id:
            df['msg'] = df[['trade_id', 'msg']].apply(lambda x: f'trade ID: {x["trade_id"]}<br>{x["msg"]}', axis=1)

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['display_odds'],
                text=df['msg'],
                mode='lines+markers',
                name=f'trade {i}',
                **display_config.get('chart_args', {}),
            ),
            **display_config.get('trace_args', {}),
        )




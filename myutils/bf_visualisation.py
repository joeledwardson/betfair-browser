from plotly.subplots import make_subplots
import plotly.graph_objects as go
from myutils import betting
import numpy as np
from myutils import bf_strategy
from betfairlightweight import APIClient


# row and col are converted from 0-index to 1-index
def _plot_selection(fig, df_selection, row, col):
    def _plot(df_col, name, secondary_y=False):
        fig.add_trace(
            go.Scatter(
                x=df_selection.index,
                y=df_selection[df_col],
                mode='lines',
                name=name),
            row=row + 1,
            col=col + 1,
            secondary_y=secondary_y)

    # _plot('back', 'best back')
    # _plot('lay', 'best lay')
    _plot('ltp', 'last traded price')
    _plot('oc', 'oddschecker')
    _plot('tv', 'traded volume', secondary_y=True)

    # fig.update_yaxes(dict(rangemode='tozero'))


def plot_market(trading: APIClient, dir_path, market_id, n_cols, pre_minutes):

    l = bf_strategy.get_hist_stream_data(
        trading,
        bf_strategy.get_hist_stream_path(dir_path, market_id))

    oc_df = bf_strategy.get_hist_oc_df(
        bf_strategy.get_hist_oc_path(dir_path, market_id))

    cat = bf_strategy.get_hist_cat(
        bf_strategy.get_hist_cat_path(dir_path, market_id))

    if (l is None) or (oc_df is None) or (cat is None):
        return

    name_id_map = betting.get_names(cat, name_attr='runner_name', name_key=True)
    oc_df = bf_strategy.process_oc_df(oc_df, name_id_map)
    if oc_df is None:
        return

    names = list(name_id_map.keys())
    oc_max = oc_df.max(axis=1)
    l_trim = betting.get_recent_records(l, pre_minutes, cat.market_start_time)
    df = betting.runner_data(l_trim,
        additional_columns={
            'tv': lambda runner: betting.traded_runner_vol(
                runner, is_dict=True)})
    n_traces = len(names)

    n_rows = int(np.ceil(n_traces / n_cols))

    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        subplot_titles=names,
        specs=[[{"secondary_y": True} for i in range(n_cols)] for j in range(n_rows)]
    )

    for i, selection_id in enumerate(name_id_map.values()):
        df_selection = df[df['selection_id'] == selection_id].copy()
        df_selection['oc'] = oc_max[selection_id]
        _plot_selection(fig, df_selection, row=int(np.floor(i / n_cols)), col=i % n_cols)

    fig.update_layout(
        showlegend=False,
        title=f'{cat.event.name} {betting.event_time(cat.market_start_time)}')
    return fig

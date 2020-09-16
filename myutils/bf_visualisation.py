from plotly.subplots import make_subplots
import plotly.graph_objects as go
from plotly import express as px
from myutils import betting, bf_strategy, generic
import numpy as np
import pandas as pd
from datetime import timedelta
from typing import List, Dict
import statsmodels.api as sm
from betfairlightweight import APIClient
from betfairlightweight.resources.bettingresources import PriceSize, RunnerBook, MarketBook


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


# start from 'current_index' in 'records', work backwards for 'seconds_window' seconds and return the last index
# that is within the window
def get_index_window(records: List, current_index, seconds_window, f_pt=lambda r, i: r[i][0].publish_time):
    window_i = current_index
    t = f_pt(records, window_i)
    while window_i - 1 >= 0 and (t - f_pt(records, window_i)).total_seconds() <= seconds_window:
        window_i -= 1
    return window_i




def get_regressions(tvdiffs, regression_seconds, required_prices=3):
    regressions = []

    t = tvdiffs.index[0]
    n = tvdiffs.shape[0]

    i0 = 0
    i1 = 0

    while t < tvdiffs.index[-1]:

        # increment time counter
        t = t + timedelta(seconds=1)

        # increment window bottom index
        while i0 < n and tvdiffs.index[i0] < (t - timedelta(seconds=regression_seconds)):
            i0 += 1

        # increment window top index
        while i1 + 1 < n and tvdiffs.index[i1 + 1] < t:
            i1 += 1

        # if possible, decrease window bottom to include previous value
        i0_extra = i0
        if i0_extra > 0:
            i0_extra -= 1

        # if possible, increase window top to include next value
        i1_extra = i1
        if i1_extra + 1 < n:
            i1_extra += 1

        # slice records
        recs = tvdiffs[i0_extra: i1_extra + 1]

        # excluding extra top/bottom records, check that there are sufficient price changes
        n_prices = tvdiffs[i0: i1 + 1]['price'].unique().shape[0]
        if n_prices < required_prices:
            continue

        # get timestamps in list form
        x = list(recs.index)

        # if extra value before window bottom is used, limit to window start time
        if i0_extra < i0:
            x[0] = t - timedelta(seconds=regression_seconds)

        # if extra value above window top is used, limit to window end time
        if i1_extra > i1:
            x[-1] = t

        y = list(recs['price'])
        w = list(recs['size'])

        # convert to negative seconds before current time
        x_s = [(r - t).total_seconds() for r in x]
        X = np.column_stack([x_s])
        X = sm.add_constant(X)

        mod_wls = sm.WLS(y, X, weights=w)
        res_wls = mod_wls.fit()
        y_pred = res_wls.predict(X)

        regressions += [
            {
                'x': x,  # [(t + timedelta(seconds=s)) for s in x_pred],
                'y': y_pred,
                'y_actual': y,
                'r2': res_wls.rsquared
            }
        ]

    return regressions


def i_prev(i):
    return max(i - 1, 0)
def i_next(i, n):
    return min(i + 1, n - 1)

def fig_historical(records: List[List[MarketBook]], selection_id):

    windows = bf_strategy.Windows()
    features: Dict[str, bf_strategy.RunnerFeatureBase] = {
        'ltp': bf_strategy.RunnerFeatureLTP(selection_id),
        'ltp min': bf_strategy.RunnerFeatureTradedWindowMin(selection_id, 60, windows),
        'ltp max': bf_strategy.RunnerFeatureTradedWindowMax(selection_id, 60, windows),
        'wom': bf_strategy.RunnerFeatureWOM(selection_id, candlestick_s=2, wom_ticks=5)
    }

    default_plot_config = {
        'chart': go.Scatter,
        'chart_args': {
            'mode': 'lines'
        },
        'trace_args': {},
    }

    feature_plot_config = {
        'wom': {
            'chart': go.Candlestick,
            'chart_args': {},
            'trace_args': {
                'secondary_y': True
            }
        }
    }


    recs = []
    dts = []

    for i in range(len(records)):
        new_book = records[i][0]
        recs.append(new_book)
        dts.append(new_book.publish_time)
        windows.update_windows(recs, new_book)

        runner_index = next((i for i, r in enumerate(new_book.runners) if r.selection_id==selection_id), None)
        for feature in features.values():
            feature.process_runner(recs, new_book, windows, runner_index)

    fig = make_subplots(specs=[[{'secondary_y': True}]])
    for f_name, f in features.items():

        chart_func = feature_plot_config.get(f_name, {}).get('chart',       default_plot_config['chart'])
        chart_args = feature_plot_config.get(f_name, {}).get('chart_args',  default_plot_config['chart_args'])
        trace_args = feature_plot_config.get(f_name, {}).get('trace_args',  default_plot_config['trace_args'])
        trace_data = f.get_data()

        chart = chart_func(
            name=f_name,
            **trace_data,
            **chart_args)

        fig.add_trace(chart, **trace_args)


    return fig


def plot_windows(records, selection_id, window_s=60, tv_s=1) -> go.Figure:
    rdat = betting.runner_data(
        records,
        additional_columns={
            'tv_total': lambda r: r.total_matched,
            'tv_ladder': lambda r: r.ex.traded_volume,
            'back': lambda r: betting.best_price(r.ex.available_to_back),
            'lay': lambda r: betting.best_price(r.ex.available_to_lay)},
        runner_filter=lambda r:r.selection_id==selection_id)

    # rdat = rdat[rdat['selection_id'] == selection_id]

    window_mins = []
    window_maxs = []
    w_index = 0

    tv_dts = []
    tv_incs = []
    tv_book_split = []
    tv_index = 0
    last_tv_update = rdat.index[0]

    for index, dt in enumerate(rdat.index):
        w_index = bf_strategy.update_index_window(
            records=rdat,
            current_index=index,
            seconds_window=window_s,
            window_index=w_index,
            f_pt=lambda r, i: r.index[i])
        tv_diff = betting.get_record_tv_diff(
            rdat['tv_ladder'][index],
            rdat['tv_ladder'][w_index],
            is_dict=True)
        prices = [tv['price'] for tv in tv_diff]
        window_mins.append(min(prices) if prices else None)
        window_maxs.append(max(prices) if prices else None)

        if (dt - last_tv_update).total_seconds() >= tv_s:

            tv_index = bf_strategy.update_index_window(
                records=rdat,
                current_index=index,
                seconds_window=tv_s,
                window_index=tv_index,
                f_pt=lambda r, i: r.index[i]
            )
            tv_cur = rdat['tv_total'][index]
            tv_prv = rdat['tv_total'][i_prev(tv_index)]
            tv_increase = (tv_cur or 0) - (tv_prv or 0)

            best_back = rdat['back'][index] or 0
            total_diff = sum([x['size'] for x in tv_diff])
            back_diff = sum([x['size'] for x in tv_diff if x['price'] >= best_back])

            tv_book_split.append(back_diff/total_diff if total_diff else 0)


            last_tv_update = dt

            tv_dts.append(dt)
            tv_incs.append(tv_increase)

    window_maxs = pd.Series(window_maxs, index=rdat.index).rolling('5s').mean()
    window_mins = pd.Series(window_mins, index=rdat.index).rolling('5s').mean()


        # print(f'done {index+1} of {rdat.shape[0]} records')

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            name='traded vol increase',
            x=tv_dts,
            y=tv_incs,
            width=1000*tv_s, # width specified in milliseconds
            opacity=0.4,
            marker_color=tv_book_split,
        ),
        secondary_y=True)
    fig.add_trace(
        go.Scatter(
            name='traded price window min',
            x=rdat.index,
            y=window_mins,
            mode='lines',
            line=dict(dash='dot')))
    fig.add_trace(
        go.Scatter(
            name='traded price window max',
            x=rdat.index,
            y=window_maxs,
            mode='lines',
            line=dict(dash='dot')))
    fig.add_trace(
        go.Scatter(
            name='best back',
            x=rdat.index,
            y=rdat['back'],
            mode='lines',
            opacity=0.3))
    fig.add_trace(
        go.Scatter(
            name='best lay',
            x=rdat.index,
            y=rdat['lay'],
            mode='lines',
            opacity=0.3))

    fig.add_trace(
        go.Scatter(
            name='last traded price',
            x=rdat.index,
            y=rdat['ltp'],
            mode='lines'))

    return fig


def fig_to_file(fig: go.Figure, file_path, mode='a'):
    with generic.create_dirs(open)(file_path, mode) as f:
        f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))


def plot_regressions(records, selection_id, regression_seconds, r2_show=0.8, required_prices=3, show_tv=True):
    tvdiffs = betting.get_tv_diffs(records, selection_id, is_dict=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            name='traded volume diffs',
            x=tvdiffs.index,
            y=tvdiffs['price'],
            mode='markers',
            marker=dict(color=tvdiffs['size']),
            hoverinfo="none"
        ))

    rdat = betting.runner_data(records, additional_columns={'tv': lambda r: r.total_matched})
    rdat = rdat[rdat['selection_id'] == selection_id]
    fig.add_trace(
        go.Scatter(
            name='last traded price',
            x=rdat.index,
            y=rdat['ltp'],
            mode='lines',
            hoverinfo="none"))

    fig.add_trace(
        go.Scatter(
            name='traded volume',
            x=rdat.index,
            y=rdat['tv'],
            mode='lines'
        ),
        secondary_y=True
    )

    regs = get_regressions(tvdiffs, regression_seconds, required_prices)
    for r in regs:
        if r['r2'] >= r2_show:
            fig.add_trace(
                go.Scatter(
                    mode='lines',
                    x=r['x'],
                    y=r['y'],
                    text=[f"rsquared: {r['r2']}" for _ in r['x']],
                    showlegend=False))
    return fig
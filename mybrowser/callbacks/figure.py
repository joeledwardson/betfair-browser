import re
from datetime import datetime, timedelta
from typing import List, Dict, Union, Optional
from dash.dependencies import Output, Input, State
import logging
from plotly import graph_objects as go
import traceback
from myutils import dashutils
from myutils.dashutils import Config, TDict, dict_callback, triggered_id
from myutils import timing
import mytrading.exceptions
from ..session import Session, LoadedMarket, Notification, post_notification
from mytrading.strategy.feature.features import RFBase

from ..exceptions import SessionException

# override visual logger with custom logger
active_logger = logging.getLogger(__name__)


def get_ids(cell: Union[None, Dict], id_list: List[int], notifs: List[Notification]) -> List[int]:
    """
    get a list of selection IDs for runners on which to plot charts
    if `do_all` is True, then simply return complete `id_list` - if not, take row ID from cell as single selection ID
    for list and validate
    """

    # determine if 'all feature plots' clicked as opposed to single plot
    do_all = triggered_id() == 'button-all-figures'

    # do all selection IDs if requested
    if do_all:
        return id_list

    # get selection ID of runner from active runner cell, or abort on fail
    if not cell:
        post_notification(notifs, 'warning', 'Figure', 'no cell selected')
        return []

    if 'row_id' not in cell:
        post_notification(notifs, 'warning', 'Figure', 'row ID not found in active cell info')
        return []

    sel_id = cell['row_id']
    if not sel_id:
        post_notification(notifs, 'warning', 'Figure', f'selection ID is blank')
        return []
    return [sel_id]


def get_chart_offset(offset: str, notifs: List[Notification]) -> Optional[timedelta]:
    """
    get chart offset based on HH:MM:SS form, return datetime on success, or None on fail
    """
    # if html trims off the seconds part of hh:mm:ss then add it back on
    if re.match(r'^\d{2}:\d{2}$', offset):
        offset = offset + ':00'

    if offset:
        if re.match(r'^\d{2}:\d{2}:\d{2}$', offset):
            try:
                t = datetime.strptime(offset, "%H:%M:%S")
                return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
            except ValueError:
                post_notification(notifs, 'warning', 'Figure', f'cannot process chart offset "{offset}"')
    return None


def cb_fig(app, shn: Session):
    @dict_callback(
        app=app,
        inputs_config={
            'buttons': [
                Input('button-figure', 'n_clicks'),
                Input('button-all-figures', 'n_clicks')
            ]
        },
        outputs_config={
            'table': Output('table-timings', 'data'),
            'loading': Output('loading-out-figure', 'children'),
            'notifications': Output('notifications-figure', 'data'),
        },
        states_config={
            'selected-market': State('selected-market', 'data'),
            'cell': State('table-runners', 'active_cell'),
            'offset': State('input-chart-offset', 'value'),
            'feature-config': State('input-feature-config', 'value'),
            'plot-config': State('input-plot-config', 'value'),
        }
    )
    def figure_callback(outputs: TDict, inputs: TDict, states: TDict):
        """
        create a plotly figure based on selected runner when "figure" button is pressed
        """
        notifs = outputs['notifications'] = []
        outputs['table'] = []
        outputs['loading'] = ''

        if triggered_id() != 'button-figure' and triggered_id() != 'button-all-figures':
            return

        if not states['selected-market']:
            return

        # deserialise market info
        shn.deserialise_loaded_market(states['selected-market'])

        # get datetime/None chart offset from time input
        offset_dt = get_chart_offset(states['offset'], notifs)
        secs = offset_dt.total_seconds() if offset_dt else 0

        # get selected IDs and plot
        sel_ids = get_ids(states['cell'], list(states['selected-market'].keys()), notifs)
        reg = timing.TimingRegistrar()

        def update_reg(f: RFBase, r: timing.TimingRegistrar):
            for s in f.sub_features.values():
                r = update_reg(f, r)
            return f.timing_reg + r

        try:
            # shn.ftr_update()  # update feature & plot configs
            for selection_id in sel_ids:
                features = shn.fig_plot(
                    market_info=states['selected-market'],
                    selection_id=selection_id,
                    secs=secs,
                    ftr_key=states['feature-config'],
                    plt_key=states['plot-config']
                )
                for f in features.values():
                    reg = update_reg(f, reg)

        except (ValueError, TypeError, mytrading.exceptions.FigureException, SessionException) as e:
            post_notification(notifs, 'warning', 'Figure', f'plot error: {e}\n{traceback.format_exc()}')

        summary = reg.get_timings_summary()
        if not summary:
            post_notification(notifs, 'warning', 'Figure', 'no timings on which to produce table')
        else:
            for s in summary:
                s['level'] = s['function'].count('.')
            outputs['table'] = shn.tms_get(summary)



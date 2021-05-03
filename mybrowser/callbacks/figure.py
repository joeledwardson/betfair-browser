import re
from datetime import datetime, timedelta
from typing import List, Dict, Union, Optional
from dash.dependencies import Output, Input, State
import logging
from plotly import graph_objects as go
import traceback

import mytrading.exceptions
import myutils.mydash
from myutils import mytiming
from ..session import Session, SessionException


# override visual logger with custom logger
active_logger = logging.getLogger(__name__)
counter = myutils.mydash.Intermediary()


def get_ids(cell, id_list) -> List[int]:
    """
    get a list of selection IDs for runners on which to plot charts
    if `do_all` is True, then simply return complete `id_list` - if not, take row ID from cell as single selection ID
    for list and validate
    """

    # determine if 'all feature plots' clicked as opposed to single plot
    do_all = myutils.mydash.triggered_id() == 'button-all-figures'

    # do all selection IDs if requested
    if do_all:
        return id_list

    # get selection ID of runner from active runner cell, or abort on fail
    if not cell:
        active_logger.warning('no cell selected')
        return []

    if 'row_id' not in cell:
        active_logger.warning(f'row ID not found in active cell info')
        return []

    sel_id = cell['row_id']
    if not sel_id:
        active_logger.warning(f'selection ID is blank')
        return []
    return [sel_id]


def get_chart_offset(chart_offset_str) -> Optional[timedelta]:
    """
    get chart offset based on HH:MM:SS form, return datetime on success, or None on fail
    """
    if re.match(r'^\d{2}:\d{2}:\d{2}$', chart_offset_str):
        try:
            t = datetime.strptime(chart_offset_str, "%H:%M:%S")
            return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
        except ValueError:
            pass
    return None


def cb_fig(app, shn: Session):
    @app.callback(
        output=[
            Output('table-timings', 'data'),
            Output('loading-out-figure', 'children'),
            Output('intermediary-figure', 'children'),
        ],
        inputs=[
            Input('button-figure', 'n_clicks'),
            Input('button-all-figures', 'n_clicks'),
        ],
        state=[
            State('table-runners', 'active_cell'),
            State('input-chart-offset', 'value'),
            State('input-feature-config', 'value'),
            State('input-plot-config', 'value')
        ]
    )
    def fig_button(clicks0, clicks1, cell, offset_str, ftr_key, plt_key):
        """
        create a plotly figure based on selected runner when "figure" button is pressed
        """

        ret = [
            list(),
            '',
            counter.next()
        ]

        if myutils.mydash.triggered_id() != 'button-figure' and myutils.mydash.triggered_id() != 'button-all-figures':
            return ret

        # get datetime/None chart offset from time input
        offset_dt = get_chart_offset(offset_str)
        secs = offset_dt.total_seconds() if offset_dt else 0

        # get selected IDs and plot
        sel_ids = get_ids(cell, list(shn.mkt_rnrs.keys()))
        try:
            shn.ftr_update()  # update feature & plot configs
            for selection_id in sel_ids:
                shn.fig_plot(selection_id, secs, ftr_key, plt_key)
        except (ValueError, TypeError, mytrading.exceptions.FigureException, SessionException) as e:
            active_logger.error(f'plot error: {e}\n{traceback.format_exc()}')

        ret[0] = shn.tms_get()
        mytiming.clear_timing_register()
        return ret

    @app.callback(
        Output('modal-timings', 'is_open'),
        [Input('button-timings', 'n_clicks'), Input('modal-close-timings', 'n_clicks')]
    )
    def modal_timings(n1, n2):
        return myutils.mydash.triggered_id() == 'button-timings'


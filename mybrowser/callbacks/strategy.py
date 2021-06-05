from __future__ import annotations
from dash.dependencies import Output, Input, State
import dash_html_components as html

import json
from typing import List, Dict, Any, Optional
from myutils import mydash
import logging
from ..session import Session, Notification as Notif, NotificationType as NType
from mytrading.strategy import tradetracker as tt

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = mydash.Intermediary()
strat_counter = mydash.Intermediary()


def cb_strategy(app, shn: Session):
    @app.callback(
        output=[
            Output('table-strategies', 'data'),
        ],
        inputs=[
            Input('interval-component', 'n_intervals')
        ]
    )
    def strat_intermediary(n_intervals):
        return []


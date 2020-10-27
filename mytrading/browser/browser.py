from __future__ import annotations
import dash
import logging
import argparse
from .data import DashData
from .callbacks import market_callback, file_table_callback, figure_callback, orders_callback
from .layout import get_layout
from datetime import timedelta


def run_browser(debug: bool, default_chart_offset: timedelta, input_dir: str):
    gdd = DashData(input_dir)

    app = dash.Dash(__name__)
    logging.basicConfig(level=logging.INFO)
    app.layout = get_layout(input_dir, gdd, default_chart_offset)

    file_table_callback(app, gdd, input_dir)
    market_callback(app, gdd, input_dir)
    figure_callback(app, gdd, input_dir)
    orders_callback(app, gdd, input_dir)

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False)

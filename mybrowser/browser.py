from __future__ import annotations
import dash
import logging
import argparse
from typing import Optional
from .data import DashData
from .callbacks.figure import figure_callback
from .callbacks.files import file_table_callback
from .callbacks.orders import orders_callback
from .callbacks.market import market_callback
from .callbacks.featureconfigs import feature_configs_callback
from .callbacks.libs import libs_callback
from .layout import get_layout
from datetime import timedelta


def run_browser(
        debug: bool,
        default_chart_offset: timedelta,
        input_dir: str,
        feature_configs_dir: Optional[str] = None,
        plot_configs_dir: Optional[str] = None,
        start_dir: Optional[str] = None,
        initial_feature_conf: Optional[str] = None,
        initial_plot_conf: Optional[str] = None,
):
    """
    run dash app mybrowser - input_dir specifies input directory for entry point for mybrowser but also expected root for:
    - "historical" dir
    - "recorded" dir
    """
    gdd = DashData(input_dir, feature_configs_dir=feature_configs_dir, plot_configs_dir=plot_configs_dir)

    if start_dir:
        gdd.file_tracker.update(start_dir)

    app = dash.Dash(__name__)
    logging.basicConfig(level=logging.INFO)
    app.layout = get_layout(
        input_dir=input_dir,
        dash_data=gdd,
        chart_offset=default_chart_offset,
        initial_feature_conf=initial_feature_conf,
        initial_plot_conf=initial_plot_conf,
    )

    file_table_callback(app, gdd, input_dir)
    market_callback(app, gdd, input_dir)
    figure_callback(app, gdd, input_dir)
    orders_callback(app, gdd, input_dir)
    feature_configs_callback(app, gdd, input_dir)
    libs_callback(app)

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False)

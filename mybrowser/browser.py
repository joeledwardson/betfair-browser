from __future__ import annotations
import dash
import logging
from typing import Optional
from .data import DashData
from . import callbacks
from .layout import get_layout
from .logger import cb_logger
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
    gdd = DashData(
        input_dir=input_dir,
        feature_configs_dir=feature_configs_dir,
        plot_configs_dir=plot_configs_dir,
        logger=cb_logger,
    )

    if start_dir:
        gdd.file_tracker.update(start_dir)

    app = dash.Dash(__name__)
    app.layout = get_layout(
        input_dir=input_dir,
        dash_data=gdd,
        chart_offset=default_chart_offset,
        initial_feature_conf=initial_feature_conf,
        initial_plot_conf=initial_plot_conf,
    )

    callbacks.files.file_table_callback(app, gdd, input_dir)
    callbacks.market.market_callback(app, gdd, input_dir)
    callbacks.figure.figure_callback(app, gdd, input_dir)
    callbacks.orders.orders_callback(app, gdd, input_dir)
    callbacks.featureconfigs.feature_configs_callback(app, gdd, input_dir)
    callbacks.libs.libs_callback(app)
    callbacks.log.log_callback(app)

    logging.root.setLevel(logging.INFO)

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False)

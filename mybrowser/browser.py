from __future__ import annotations
import dash
from typing import Optional, List
from .data import DashData
from . import callbacks
from .layout import get_layout
from datetime import timedelta


def run_browser(
        debug: bool,
        default_chart_offset: timedelta,
        input_dir: str,
        feature_config_default: str,
        plot_config_default: Optional[str] = None,
        feature_configs_dir: Optional[str] = None,
        plot_configs_dir: Optional[str] = None,
        start_dir: Optional[str] = None,
        feature_config_initial: Optional[str] = None,
        plot_config_initial: Optional[str] = None,
        external_stylesheets: Optional[List[str]] = None,
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
        feature_configs_default=feature_config_default,
    )
    gdd.plot_config_default=plot_config_default

    if start_dir:
        gdd.file_tracker.update(start_dir)

    # if not external_stylesheets:
    #     external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

    app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
    app.layout = get_layout(
        input_dir=input_dir,
        dash_data=gdd,
        chart_offset=default_chart_offset,
        feature_config_initial=feature_config_initial,
        plot_config_initial=plot_config_initial,
    )

    callbacks.files.file_table_callback(app, gdd, input_dir)
    callbacks.market.market_callback(app, gdd, input_dir)
    callbacks.figure.figure_callback(app, gdd, input_dir)
    callbacks.orders.orders_callback(app, gdd, input_dir)
    callbacks.featureconfigs.feature_configs_callback(app, gdd, input_dir)
    callbacks.libs.libs_callback(app)
    callbacks.log.log_callback(app)

    # turn of dev tools prop check to disable time input error
    app.run_server(debug=debug, dev_tools_props_check=False)

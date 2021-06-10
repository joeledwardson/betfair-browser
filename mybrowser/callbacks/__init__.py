from dash.dependencies import Output, Input, State
import dash_html_components as html
import logging
from myutils import mydash
from typing import List

from .configs import cb_configs
from .figure import cb_fig
from .libs import cb_libs
from .logger import cb_logs
from .market import cb_market
from .orders import cb_orders
from .runners import cb_runners
from .strategy import cb_strategy
from ..exceptions import UrlException


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def _tbl_disabler(app, table_id: str, output_ids: List[str], check_row_id=True):
    """
    disable dash elements based on active_cell of dash datatable
    """
    @app.callback(
        output=[Output(x, 'disabled') for x in output_ids],
        inputs=[
            Input(table_id, 'active_cell'),
        ],
    )
    def btn_disable(active_cell):
        if active_cell is not None:
            if not check_row_id or ('row_id' in active_cell and active_cell['row_id']):
                return [False] * len(output_ids)
        return [True] * len(output_ids)


def _right_panel_callback(app, panel_id: str, open_id: str, close_id: str):
    """
    toggle "right-not-collapsed" css class to open and close a side panel based on open/close buttons
    """
    @app.callback(
        Output(panel_id, "className"),
        [
            Input(open_id, "n_clicks"),
            Input(close_id, "n_clicks")
        ],
        State(panel_id, "className")
    )
    def toggle_classname(n1, n2, class_names: str):
        # CSS class toggles sidebar
        classes = mydash.CSSClassHandler(class_names)
        if mydash.triggered_id() == open_id:
            return str(classes + "right-not-collapsed")
        else:
            return str(classes - "right-not-collapsed")


def cb_display(app):
    outputs = [
        Output("container-market", "hidden"),
        Output("container-filters-market", "hidden"),
        Output("container-runners", "hidden"),
        Output("container-filters-plot", "hidden"),
        Output("container-timings", "hidden"),
        Output("container-logs", "hidden"),
        Output("container-strategy", "hidden"),
        Output("container-filters-strategy", "hidden"),
        Output("container-orders", "hidden")
    ]

    # set the content according to the current pathname
    @app.callback(outputs, Input("url", "pathname"))
    def render_page_content(pathname):
        if pathname == "/":
            displays = ["container-market", "container-filters-market"]
        elif pathname == "/runners":
            displays = ["container-runners", "container-filters-plot"]
        elif pathname == "/timings":
            displays = ["container-timings"]
        elif pathname == "/logs":
            displays = ["container-logs"]
        elif pathname == "/strategy":
            displays = ["container-strategy", "container-filters-strategy"]
        elif pathname == "/orders":
            displays = ["container-orders"]
        else:
            displays = list()
        return [False if element.component_id in displays else True for element in outputs]

    # open/close right panel callbacks
    _right_panel_callback(app, "container-filters-market", "btn-session-filter", "btn-right-close")
    _right_panel_callback(app, "container-filters-strategy", "btn-strategy-filter", "btn-strategy-close")

    # market download button hide condition
    _tbl_disabler(app, 'table-market-session', [
        'button-runners',
        'nav-runners'
    ], True)

    # strategy download button hide condition
    _tbl_disabler(app, 'table-strategies', [
        'btn-strategy-download',
        'nav-strategy-download',
        'btn-strategy-delete'
    ], True)

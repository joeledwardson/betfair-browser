from dash.dependencies import Output, Input, State
import dash_html_components as html
import logging
from myutils import mydash

from .configs import cb_configs
from .figure import cb_fig
from .libs import cb_libs
from .logger import cb_logs
from .market import cb_market
from .orders import cb_orders
from .runners import cb_runners
from ..exceptions import UrlException


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


def cb_display(app):
    outputs = [
        Output("container-market", "hidden"),
        Output("container-filters-market", "hidden"),
        Output("container-runners", "hidden"),
        Output("container-filters-plot", "hidden"),
        Output("container-timings", "hidden"),
        Output("container-logs", "hidden")
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
        else:
            displays = list()

        return [False if element.component_id in displays else True for element in outputs]
from typing import List, Tuple, Dict
from betfairlightweight.resources.bettingresources import MarketBook
from ..utils.security import get_api_client
from .filetracker import FileTracker
from .marketinfo import MarketInfo


class ButtonTracker:
    """track the number of clicks for a button"""

    def __init__(self):
        self.n_clicks = 0

    def is_pressed(self, n_clicks) -> bool:
        return n_clicks > self.n_clicks

    def update(self, n_clicks):
        self.n_clicks = n_clicks

    def __repr__(self):
        return str(self.n_clicks)


class DashData:

    def __init__(self, input_dir: str, feature_configs_dir=None):

        # hold list of records from active historical file
        self.record_list: List[List[MarketBook]] = []

        # track files browser
        self.file_tracker = FileTracker(input_dir)

        # API client instance
        self.trading = get_api_client()

        # market information of active market
        self.market_info = MarketInfo()

        # directory of market information for active market
        self.market_dir = ''

        # dict of {selection ID: starting odds} of runners in active market
        self.start_odds: Dict[int, float] = {}

        # directory that holds feature configurations
        self.feature_configs_dir = feature_configs_dir

        # dictionary holding feature configurations of directory indicated above
        self.feature_configs = dict()

    def clear_market(self):
        self.market_info = None
        self.market_dir = ''
        self.start_odds = {}



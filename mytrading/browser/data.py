from typing import List, Tuple, Dict
from betfairlightweight.resources.bettingresources import MarketBook
from mytrading.utils.security import get_api_client
from mytrading.browser.filetracker import FileTracker
from mytrading.browser.marketinfo import MarketInfo


class ButtonTracker:
    """track the number of clicks for a button"""

    def __init__(self):
        self.n_clicks = 0

    def update(self, n_clicks) -> bool:
        old_clicks = self.n_clicks
        self.n_clicks = n_clicks
        return n_clicks > old_clicks


class DashData:

    def __init__(self, input_dir: str):
        self.record_list: List[List[MarketBook]] = []
        self.button_trackers: Dict[str, ButtonTracker] = {
            'profit': ButtonTracker(),
            'return': ButtonTracker(),
        }
        self.file_tracker = FileTracker(input_dir)
        self.trading = get_api_client()
        self.start_odds: Dict[int, float] = {}
        self.market_info = MarketInfo()
        self.market_dir = ''
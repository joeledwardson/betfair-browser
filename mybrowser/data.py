from typing import List, Tuple, Dict, Optional
from betfairlightweight.resources.bettingresources import MarketBook

from mytrading.utils import security as mysecurity
from mytrading.utils.bettingdb import BettingDB


# TODO - how to remove globals to make this multiprocess valid? strategy id, runner names, market info, start odds
#  could all be cached or stored in hidden divs.
class DashData:

    def init_db(self, **db_kwargs):
        self.betting_db = BettingDB(**db_kwargs)

    def __init__(self):

        # market info - selected strategy, runner names, market meta dict, and streaming update list
        self.strategy_id = None
        self.runner_names = {}
        self.db_mkt_info = {}
        self.start_odds: Dict[int, float] = {} # dict of {selection ID: starting odds} of runners in active market
        self.record_list: List[List[MarketBook]] = []

        # betting database instance
        self.betting_db: Optional[BettingDB] = None

        # API client instance
        self.trading = mysecurity.get_api_client()

        # dictionary holding of {file name: config} for feature/plot configurations
        self.feature_configs = dict()
        self.plot_configs = dict()

    def clear_market(self):
        self.runner_names = {}
        self.db_mkt_info = {}
        self.start_odds = {}
        self.record_list = []




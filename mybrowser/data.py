from typing import List, Tuple, Dict, Optional
from betfairlightweight.resources.bettingresources import MarketBook

from mytrading.utils import security as mysecurity
from mytrading.utils.bettingdb import BettingDB


class DashData:

    def init_db(self):
        self.betting_db = BettingDB()

    def __init__(
            self,
            input_dir: str='',
            feature_configs_default='',
            feature_configs_dir=None,
            plot_configs_dir=None,
    ):

        self.strategy_id = None
        self.runner_names = {}
        self.db_mkt_info = {}

        # betting database instance
        self.betting_db: Optional[BettingDB] = None

        # hold list of records from active historical file
        self.record_list: List[List[MarketBook]] = []

        # API client instance
        self.trading = mysecurity.get_api_client()

        # dict of {selection ID: starting odds} of runners in active market
        self.start_odds: Dict[int, float] = {}

        # dictionary holding of {file name: config} for feature/plot configurations
        self.feature_configs = dict()
        self.plot_configs = dict()

        # default feature/plot configuration name
        self.plot_config_default = None
        self.feature_config_default = None

    def clear_market(self):
        self.runner_names = {}
        self.db_mkt_info = {}
        self.start_odds = {}
        self.record_list = []




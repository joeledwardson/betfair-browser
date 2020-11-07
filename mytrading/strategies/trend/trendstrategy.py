"""trade between LTP max/min windows"""

from typing import Dict
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
import logging

from myutils.timing import timing_register
from ...trademachine import tradestates as basestates
from ...trademachine.trademachine import RunnerStateMachine
from ...strategy.featurestrategy import MyFeatureStrategy
from ...process.ticks.ticks import LTICKS_DECODED, tick_spread
from ...process.tradedvolume import traded_runner_vol
from ...feature.config import get_features_default_configs


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyWindowStrategy(MyFeatureStrategy):
    """
    Take breach of LTP min/max windows as drift in specific direction and back/lay in the direction of drift
    """

    def __init__(
            self,
            base_dir,
            sampling_ms,
            sampling_count,
            *args,
            **kwargs):

        super().__init__('trend', base_dir, *args, **kwargs)
        self.sampling_ms = sampling_ms
        self.sampling_count = sampling_count

    def create_state_machine(
            self,
            runner: RunnerBook,
            market: Market,
            market_book: MarketBook
    ) -> RunnerStateMachine:
        """
        get trading state machine for selected runner
        """

    def get_features_config(self) -> Dict:

        # get default features (TODO update this)
        features_config = get_features_default_configs()

        # create kwargs for sampling and moving average
        def sampling_kwargs():
            return {
                'periodic_ms': self.sampling_ms,
                'periodic_timestamps': True,
                'value_processor': 'value_processor_moving_average',
                'value_processor_args': {
                    'n_entries': self.sampling_count
                },
            }

        features_config['best back smoothed'] = {
            'name': 'RunnerFeatureBestBack',
            'kwargs': sampling_kwargs()
        }
        features_config['best lay smoothed'] = {
            'name': 'RunnerFeatureLay',
            'kwargs': sampling_kwargs()
        }
        features_config['ltp smoothed'] = {
            'name': 'RunnerFeatureLTP',
            'kwargs': sampling_kwargs()
        }
        return features_config

    def trade_machine_kwargs(
            self,
            market: Market,
            market_book: MarketBook,
            runner_index: int,
    ) -> dict:
        return {}
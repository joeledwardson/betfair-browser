from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
from flumine.order.order import OrderStatus, BetfairOrder
from flumine.order.ordertype import LimitOrder, OrderTypes

import logging
from enum import Enum
from typing import List, Dict, Union
from datetime import datetime, timedelta

from ...feature.features import RunnerFeatureBase
from ...tradetracker.tradetracker import TradeTracker
from ...process.side import select_ladder_side
from ...tradetracker.messages import MessageTypes
from ...trademachine.tradestates import TradeStateTypes
from ...process.ticks.ticks import tick_spread
from ...trademachine import tradestates


MIN_BET_AMOUNT = 2
active_logger = logging.getLogger(__name__)


class TrendTradeStateTypes(Enum):
    a=1


class TrendTradeStateIdle(tradestates.TradeStateIdle):
    def __init__(
            self,
            tick_offset: int,
            window_spread_min: int,
            ladder_spread_max: int,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.tick_offset = tick_offset
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max

    def trade_criteria(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            first_runner: bool,
            features: Dict[str, RunnerFeatureBase],
            **inputs,
    ) -> bool:

        best_back = features['best back'].last_value()
        best_lay = features['best lay'].last_value()
        ltp = features['ltp'].last_value()
        ltp_min = features['ltp_min'].last_value()
        ltp_max = features['ltp_max'].last_value()
        ladder_spread = features['spread'].last_value()

        # check that all values are not None and non-zero
        if any([x is None or x == 0 for x in [best_back, best_lay, ltp, ltp_min, ltp_max, ladder_spread]]):
            return False

        window_spread = tick_spread(ltp_min, ltp_max, check_values=False)

        if ladder_spread <= self.ladder_spread_max and window_spread >= self.window_spread_min:
            return True



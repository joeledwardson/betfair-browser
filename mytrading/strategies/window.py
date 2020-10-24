"""trade between LTP max/min windows"""
from flumine.order.order import BetfairOrder, OrderStatus
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook

import mytrading.trademachine.tradestates
from mytrading.trademachine import trademachine as bftm
from mytrading.strategy.featurestrategy import MyFeatureStrategy
from mytrading.process.ladder import BfLadderPoint, get_ladder_point
from mytrading.tradetracker.tradetracker import TradeTracker
from mytrading.process.ticks.ticks import LTICKS_DECODED, LTICKS, TICKS
from mytrading.process.prices import best_price
from mytrading.process.ladder import runner_spread
from mytrading.strategy.side import select_ladder_side, select_operator_side, invert_side
from myutils.generic import i_prev, i_next
from myutils import generic

from flumine import BaseStrategy
import logging
from typing import List, Dict
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from functools import partial
from mytrading.trademachine import tradestates
from mytrading.tradetracker.tradetracker import TradeTracker
from mytrading.process.ticks.ticks import closest_tick


class WindowTradeStateBase(tradestates.TradeStateIdle):
    """
    Idle state implements `trade_criteria()` function, to return True (indicating move to open trade place state)
    once a valid wall is detected on inputs
    """

    def enter(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        pass

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **inputs
    ):
        raise NotImplementedError


class WindowTradeStateIdle(tradestates.TradeStateIdle, WindowTradeStateBase):

    def __init__(self, max_odds, ltp_min_spread, max_ladder_spread, track_seconds, **kwargs):
        super().__init__(**kwargs)

        self.track_seconds = track_seconds
        self.max_odds = max_odds
        self.ltp_min_spread: int = ltp_min_spread
        self.max_ladder_spread: int = max_ladder_spread

        self.up: bool = True
        self.tracker_start: datetime = datetime.now()
        self.tracking: bool = False

    def validate(self, ltp: float, ltp_min: float, ltp_max: float, ladder_spread: int) -> bool:
        if ltp <= self.max_odds:
            index_min = closest_tick(ltp_min, return_index=True)
            index_max = closest_tick(ltp_max, return_index=True)
            if index_max - index_min >= self.ltp_min_spread:
                if ladder_spread <= self.max_ladder_spread:
                    return True
        return False

    def track(self, pt: datetime, direction_up: bool):
        self.tracking = True
        self.up = direction_up
        self.tracker_start = pt

    def run(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            ltp: float,
            ltp_min: float,
            ltp_max: float,
            ladder_spread: int,
    ):
        pt = market_book.publish_time

        # check if broken upper window
        if ltp > ltp_max:

            # if not tracking, start
            if not self.tracking:
                if self.validate(ltp, ltp_min, ltp_max, ladder_spread):
                    self.track(pt, direction_up=True)

            else:

                # already tracking and in right direction, check for completion of time limit
                if self.up:
                    if (pt - self.tracker_start).total_seconds() >= self.track_seconds:
                        return self.next_state

                # tracking down instead of up, switch direction
                else:
                    if self.validate(ltp, ltp_min, ltp_max, ladder_spread):
                        self.track(pt, direction_up=True)

        # check if broken lower window
        elif ltp < ltp_min:

            # if not tracking, start
            if not self.tracking:
                if self.validate(ltp, ltp_min, ltp_max, ladder_spread):
                    self.track(pt, direction_up=False)

            else:

                # already tracking and in right direction, check for completion of time limit
                if not self.up:
                    if (pt - self.tracker_start).total_seconds() >= self.track_seconds:
                        return self.next_state

                # tracking up instead of down, switch direction
                else:
                    if self.validate(ltp, ltp_min, ltp_max, ladder_spread):
                        self.track(pt, direction_up=True)

        # if here reached then have not broken upper/lower window
        else:

            # cancel active track
            self.tracking = False


class WindowTradeStateOpenPlace(tradestates.TradeStateOpenPlace):
    def place_order(
            self,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            ltp: float,
            ltp_min: float,
            ltp_max: float,
            ladder_spread: int,
            **inputs) -> BetfairOrder:

        if ltp > ltp_max:
            pass

        raise NotImplementedError
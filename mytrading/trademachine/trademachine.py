from ..tradetracker.messages import MessageTypes
from ..tradetracker.tradetracker import TradeTracker
from ..process.prices import best_price
from .tradestates import TradeStateBase

from myutils import statemachine as stm
from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
import logging
from typing import Dict
from enum import Enum

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class RunnerStateMachine(stm.StateMachine):
    """
    implement state machine for runners, logging state changes with runner ID
    """

    # override state types
    states: Dict[Enum, TradeStateBase]

    def __init__(self, states: Dict[Enum, TradeStateBase], initial_state: Enum, selection_id: int):
        super().__init__(states, initial_state)
        self.selection_id = selection_id

    def process_state_change(
            self,
            old_state: Enum,
            new_state: Enum,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **kwargs):

        # if state specifies that on entering dont print update, exit
        if not self.states[new_state].print_change_message:
            return

        # if first call then no odds information, use ltp/back/lay, or just 0 if doesnt have one
        if not len(trade_tracker._log):
            bk = market_book.runners[runner_index]
            ltp = bk.last_price_traded
            best_back = best_price(bk.ex.available_to_back)
            best_lay = best_price(bk.ex.available_to_lay)
            display_odds = ltp or best_back or best_lay or 0
            log_kwargs={
                'display_odds': display_odds,
            }
        else:
            log_kwargs = {}

        trade_tracker.log_update(
            msg_type=MessageTypes.STATE_CHANGE,
            msg_attrs={
                'old_state': str(old_state),
                'new_state': str(new_state)
            },
            dt=market_book.publish_time,
            **log_kwargs,
        )


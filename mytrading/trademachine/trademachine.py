from mytrading.tradetracker.messages import MessageTypes
from mytrading.tradetracker.tradetracker import TradeTracker
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
    def __init__(self, states: Dict[Enum, stm.State], initial_state: Enum, selection_id: int):
        super().__init__(states, initial_state)
        self.selection_id = selection_id

    def process_state_change(
            self,
            old_state,
            new_state,
            market_book: MarketBook,
            market: Market,
            runner_index: int,
            trade_tracker: TradeTracker,
            strategy: BaseStrategy,
            **kwargs):

        # if first call then no odds information, use last traded price, or just 0 if doesnt have one
        if not len(trade_tracker._log):
            log_kwargs={
                'display_odds': market_book.runners[runner_index].last_price_traded or 0,
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


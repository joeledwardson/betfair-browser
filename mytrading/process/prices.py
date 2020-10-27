from betfairlightweight.resources.bettingresources import MarketBook
import logging
from typing import List, Dict
from .getter import GETTER

active_logger = logging.getLogger(__name__)


def starting_odds(records: List[List[MarketBook]]) -> Dict:
    """get a dictionary of {selection ID: starting odds}"""
    for i in reversed(range(len(records))):
        if not records[i][0].market_definition.in_play and records[i][0].status == 'OPEN':
            runner_odds = {}
            for runner in records[i][0].runners:
                price = best_price(runner.ex.available_to_back)
                if price is not None:
                    runner_odds[runner.selection_id] = price
            return runner_odds
    else:
        return {}


def best_price(available: List, is_dict=True) -> float:
    """get best price from available ladder of price sizes, returning None if empty"""
    return GETTER[is_dict](available[0], 'price') if available else None

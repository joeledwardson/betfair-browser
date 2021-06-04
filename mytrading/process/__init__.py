from __future__ import annotations
import operator
from dataclasses import dataclass
import logging
from datetime import datetime
from typing import Dict, List, Union, Optional, Callable
from betfairlightweight.resources import MarketBook, RunnerBook, MarketDefinitionRunner
from betfairlightweight.resources.bettingresources import RunnerBookEX
from flumine.order.trade import Trade

from .ticks import LTICKS, LTICKS_DECODED, TICKS, TICKS_DECODED
from myutils import mygeneric, mytiming
from ..exceptions import BfProcessException
from . import oddschecker as oc

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


GETTER = {
    # Use True to return dictionary getter, False to return attribute getter
    # betfairlightweight RunnerBookEx ojects available_to_back, available_to_lay, traded_volume are inconsistent in
    # appearing as lists of dicts with 'price' and 'size', and lists of PriceSize objects.
    True: dict.get,
    False: getattr
}


@dataclass
class BfLadderPoint:
    """single point of betfair ladder, on back/lay side, with associated price & size and index of price in complete
    betfair tick ladder"""
    price: float
    size: float
    tick_index: int
    side: str

    def __str__(self):
        return f'{self.side} at {self.price} for £{self.size:.2f}, tick index {self.tick_index}'

    @staticmethod
    def get_ladder_point(price: float, size: float, side: str) -> BfLadderPoint:
        """get ladder point instance with tick index"""
        # max decimal points is 2 for betfair prices
        price = round(price, 2)
        if price not in LTICKS_DECODED:
            raise BfProcessException(f'failed to create ladder point at price {price}')
        if side != 'BACK' and side != 'LAY':
            raise BfProcessException(f'failed to create ladder point with side "{side}"')
        return BfLadderPoint(
            price=price,
            size=size,
            tick_index=LTICKS_DECODED.index(price),
            side=side
        )


@dataclass
class MatchBetSums:
    """
    Matched bet sums to record:
    - total stakes of back bets
    - total potential profits from back bets (minus stakes)
    - total stakes of lay bets
    - total exposure of lay bets
    """
    back_stakes: float
    back_profits: float
    lay_stakes: float
    lay_exposure: float

    def outstanding_profit(self):
        """get difference between (profit/loss on selection win) minus (profit/loss on selection loss)"""
        # selection win profit is (back bet profits - lay bet exposures)
        # selection loss profit is (lay stakes - back stakes)
        return (self.back_profits - self.lay_exposure) - (self.lay_stakes - self.back_stakes)

    @staticmethod
    def get_match_bet_sums(trade: Trade) -> MatchBetSums:
        """Get match bet sums from all orders in trade"""
        back_stakes = sum([o.size_matched for o in trade.orders if o.side == 'BACK'])
        back_profits = sum([
            (o.average_price_matched - 1) * o.size_matched for o in trade.orders
            # if o.status == OrderStatus.EXECUTABLE or o.status == OrderStatus.EXECUTION_COMPLETE
            if o.side == 'BACK' and o.average_price_matched and o.size_matched
        ])

        lay_stakes = sum([o.size_matched for o in trade.orders if o.side == 'LAY'])
        lay_exposure = sum([
            (o.average_price_matched - 1) * o.size_matched for o in trade.orders
            # if o.status == OrderStatus.EXECUTABLE or o.status == OrderStatus.EXECUTION_COMPLETE
            if o.side == 'LAY' and o.average_price_matched and o.size_matched
        ])

        return MatchBetSums(
            back_stakes=back_stakes,
            back_profits=back_profits,
            lay_stakes=lay_stakes,
            lay_exposure=lay_exposure
        )


def get_runner_spread(book_ex: RunnerBookEX) -> float:
    """
    get the number of ticks spread between the back and lay side of a runner book
    returns 1000 if either side is empty
    """
    atb = book_ex.available_to_back
    atl = book_ex.available_to_lay
    if atb and atl:
        if atb[0]['price'] in LTICKS_DECODED and atl[0]['price'] in LTICKS_DECODED:
            return LTICKS_DECODED.index(atl[0]['price']) - LTICKS_DECODED.index(atb[0]['price'])
    return len(LTICKS_DECODED)


def get_names(market, name_attr='name', name_key=False) -> Dict[int, str]:
    """
    Get dictionary of {runner ID: runner name} from a market definition
    - name_attr: optional attribute name to retrieve runner name
    - name_key: optional flag to return {runner name: runner ID} with name as key instead
    """
    if not name_key:
        return {
            runner.selection_id: getattr(runner, name_attr)
            for runner in market.runners
        }
    else:
        return {
            getattr(runner, name_attr): runner.selection_id
            for runner in market.runners
        }


def get_starting_odds(records: List[List[MarketBook]]) -> Dict:
    """get a dictionary of {selection ID: starting odds} from last record where market is open"""
    for i in reversed(range(len(records))):
        if not records[i][0].market_definition.in_play and records[i][0].status == 'OPEN':
            runner_odds = {}
            for runner in records[i][0].runners:
                price = get_best_price(runner.ex.available_to_back)
                if price is not None:
                    runner_odds[runner.selection_id] = price
            return runner_odds
    else:
        return {}


def get_best_price(available: List, is_dict=True) -> float:
    """get best price from available ladder of price sizes, returning None if empty"""
    return GETTER[is_dict](available[0], 'price') if available else None


def get_ltps(market_book: MarketBook) -> Dict[int, float]:
    """get dictionary of runner ID to last traded price if last traded price is not 0 (or None), sorting with
    shortest LTP first"""
    return mygeneric.dict_sort({
        r.selection_id: r.last_price_traded
        for r in market_book.runners if r.last_price_traded
    })


def get_order_profit(sts: str, side: str, price: float, size: float) -> float:
    """
    Compute order profit from dictionary of values retrieved from a line of a file written to by TradeTracker.log_update

    Function is shamelessly stolen from `flumine.backtest.simulated.Simulated.profit`, but that requires an order
    instance which is not possible to create trade/strategy information etc
    """
    if sts == "WINNER":
        if side == "BACK":
            return round((price - 1) * size, ndigits=2)
        else:
            return round((price - 1) * -size, ndigits=2)
    elif sts == "LOSER":
        if side == "BACK":
            return -size
        else:
            return size
    else:
        return 0.0


def get_runner_book(
        runners: Union[List[RunnerBook],
        List[MarketDefinitionRunner]],
        selection_id
) -> Optional[RunnerBook]:
    """Get a runner book object by checking for match of "selection_id" attribute from a list of objects"""
    for runner in runners:
        if selection_id == runner.selection_id:
            return runner
    else:
        return None


def get_side_operator(side, invert=False) -> Callable:
    """
    generic operator selection when comparing odds
    - if side is 'BACK', returns gt (greater than)
    - if side is 'LAY', returns lt (less than)
    - set invert=True to return the other operator
    """
    if side == 'BACK':
        greater_than = True
    elif side == 'LAY':
        greater_than = False
    else:
        raise BfProcessException(f'side "{side}" not recognised')

    if invert:
        greater_than = not greater_than

    if greater_than:
        return operator.gt
    else:
        return operator.lt


def get_side_ladder(book_ex: RunnerBookEX, side) -> List[Dict]:
    """
    get selected side of runner book ex:
    - if side is 'BACK', returns 'book_ex.available_to_back'
    - if side is 'LAY', returns 'book.ex.available_to_lay'
    """
    if side == 'BACK':
        return book_ex.available_to_back
    elif side == 'LAY':
        return book_ex.available_to_lay
    else:
        raise BfProcessException(f'side "{side}" not recognised')


def side_invert(side: str) -> str:
    """
    convert 'BACK' to 'LAY' and vice-versa
    """
    if side == 'BACK':
        return 'LAY'
    elif side == 'LAY':
        return 'BACK'
    else:
        raise BfProcessException(f'side "{side}" not recognised')


def closest_tick(value: float, return_index=False, round_down=False, round_up=False):
    """
    Convert an value to the nearest odds tick, e.g. 2.10000001 would be converted to 2.1
    Specify return_index=True to get index instead of value
    """
    return mygeneric.closest_value(
        TICKS_DECODED,
        value,
        return_index=return_index,
        round_down=round_down,
        round_up=round_up
    )


def tick_spread(value_0: float, value_1: float, check_values: bool) -> int:
    """
    get tick spread between two odds values
    - if `check_values` is True and both values don't correspond to tick
    values, then 0 is returned
    - if `check_values` if False then the closest tick value is used for `value_0` and `value_1`
    """
    if check_values:
        # check that both values are valid odds
        if value_0 in LTICKS_DECODED and value_1 in LTICKS_DECODED:
            # get tick spread
            return abs(LTICKS_DECODED.index(value_0) - LTICKS_DECODED.index(value_1))
        else:
            # both values are not valid odds
            return 0
    else:
        # dont check values are valid odds, just use closet odds values
        return abs(closest_tick(value_0, return_index=True) - closest_tick(value_1, return_index=True))


def traded_runner_vol(runner: RunnerBook, is_dict=True):
    """Get runner traded volume across all prices"""
    return sum(e['size'] if is_dict else e.size for e in runner.ex.traded_volume)


def total_traded_vol(record: MarketBook):
    """Get traded volume across all runners at all prices"""
    return sum(traded_runner_vol(runner) for runner in record.runners)


def get_record_tv_diff(
        tv1: List[Dict],
        tv0: List[Dict],
        is_dict=True
) -> List[Dict]:
    """
    Get difference between traded volumes from one tv ladder to another
    use is_dict=False if `price` and `size` are object attributes, use is_dict=True if are dict keys
    """
    traded_diffs = []

    atr = GETTER[is_dict]

    # loop items in second traded volume ladder
    for y in tv1:

        # get elements in first traded volume ladder if prices matches
        m = [x for x in tv0 if atr(x, 'price') == atr(y, 'price')]

        # first element that matches
        n = next(iter(m), None)

        # get price difference, using 0 for other value if price doesn't exist
        size_diff = atr(y, 'size') - (atr(n, 'size') if m else 0)

        # only append if there is a difference
        if size_diff:
            traded_diffs.append({
                'price': atr(y, 'price'),
                'size': size_diff
            })

    return traded_diffs


def event_time(dt: datetime, localise=True) -> str:
    """
    Time of event in HH:MM, converted from betfair UTC to local
    """
    if localise:
        dt = mytiming.localise(dt)
    return dt.strftime("%H:%M")


def bf_dt(dt: datetime) -> str:
    """Datetime format to use with betfair API"""
    return dt.strftime("%Y-%m-%dT%TZ")
from flumine.order.order import OrderStatus
from flumine.order.trade import Trade
from mytrading import betting
import logging
from dataclasses import dataclass

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


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


def get_match_bet_sums(trade: Trade) -> MatchBetSums:
    """
    Get match bet sums from all orders in trade
    """

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


@dataclass
class BfLadderPoint:
    """single point of betfair ladder, on back/lay side, with associated price & size and index of price in complete
    betfair tick ladder"""
    price: float
    size: float
    tick_index: int
    side: str

    def str(self):
        return f'{self.side} at {self.price} for £{self.size:.2f}, tick index {self.tick_index}'


def get_ladder_point(price: float, size: float, side: str) -> BfLadderPoint:
    """get ladder point instance with tick index"""

    # max decimal points is 2 for betfair prices
    price = round(price, 2)
    if price in betting.LTICKS_DECODED:
        if side == 'BACK' or side == 'LAY':
            return BfLadderPoint(
                price=price,
                size=size,
                tick_index=betting.LTICKS_DECODED.index(price),
                side=side
            )
        else:
            active_logger.warning(f'failed to create ladder point with side "{side}"')
            return None
    else:
        active_logger.warning(f'failed to create ladder point at price {price}')
        return None
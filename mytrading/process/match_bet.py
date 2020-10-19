from flumine.order.trade import Trade
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



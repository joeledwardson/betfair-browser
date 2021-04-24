from dataclasses import dataclass
from betfairlightweight.resources.bettingresources import RunnerBookEX
from .ticks.ticks import LTICKS_DECODED
import logging

active_logger = logging.getLogger(__name__)


def runner_spread(book_ex: RunnerBookEX) -> float:
    """
    get the number of ticks spread between the back and lay side of a runner book
    returns 1000 if either side is empty
    """
    if book_ex.available_to_back and book_ex.available_to_back[0]['price'] in LTICKS_DECODED and \
        book_ex.available_to_lay and book_ex.available_to_lay[0]['price'] in LTICKS_DECODED:

        return LTICKS_DECODED.index(book_ex.available_to_lay[0]['price']) - \
               LTICKS_DECODED.index(book_ex.available_to_back[0]['price'])

    else:

        return len(LTICKS_DECODED)


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


def get_ladder_point(price: float, size: float, side: str) -> BfLadderPoint:
    """get ladder point instance with tick index"""

    # max decimal points is 2 for betfair prices
    price = round(price, 2)
    if price in LTICKS_DECODED:
        if side == 'BACK' or side == 'LAY':
            return BfLadderPoint(
                price=price,
                size=size,
                tick_index=LTICKS_DECODED.index(price),
                side=side
            )
        else:
            active_logger.warning(f'failed to create ladder point with side "{side}"')
            return None
    else:
        active_logger.warning(f'failed to create ladder point at price {price}')
        return None
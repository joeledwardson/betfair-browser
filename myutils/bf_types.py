from dataclasses import dataclass, field
from myutils import betting
import logging

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


@dataclass
class BfLadderPoint:
    price: float
    size: float
    tick_index: int
    side: str

    def str(self):
        return f'{self.side} at {self.price} for £{self.size}, tick index {self.tick_index}'


def get_ladder_point(price: float, size: float, side: str) -> BfLadderPoint:

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
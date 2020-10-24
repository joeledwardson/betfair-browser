from betfairlightweight.resources import MarketBook
from flumine import BaseStrategy
from flumine.markets.market import Market
import logging


active_logger = logging.getLogger(__name__)


class MyBaseStrategy(BaseStrategy):
    """
    Implementation of flumine `BaseStrategy`:
    - check_market_book() checks if book is closed
    - place_order() prints if order validation failed
    """
    def check_market_book(self, market: Market, market_book: MarketBook) -> bool:
        """
        return True (tell flumine to run process_market_book()) only executed if market not closed
        """
        if market_book.status != "CLOSED":
            return True

    # override default place order, this time printing where order validation failed
    # TODO - print reason for validation fail
    def place_order(self, market: Market, order) -> None:
        runner_context = self.get_runner_context(*order.lookup)
        if self.validate_order(runner_context, order):
            runner_context.place()
            market.place_order(order)
        else:
            active_logger.warning(f'order validation failed for "{order.selection_id}"')
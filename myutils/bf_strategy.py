from flumine import clients, BaseStrategy
from flumine.order.order import BaseOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook

from myutils import bf_feature as bff, bf_window as bfw
from myutils.timing import EdgeDetector
from datetime import timedelta
import logging
from typing import List, Dict, Optional


active_logger = logging.getLogger(__name__)


def filter_orders(orders, selection_id) -> List[BaseOrder]:
    """
    filter order to those placed on a specific runner identified by `selection_id`
    """
    return [o for o in orders if o.selection_id == selection_id]


class MyBaseStrategy(BaseStrategy):
    """
    Implementation of flumine `BaseStrategy`:
    - check_market_book() checks if book is closed
    - place_order() prints if order validation failed
    """

    def check_market_book(self, market, market_book):
        # process_market_book only executed if this returns True
        if market_book.status != "CLOSED":
            return True

    # override default place order, this time printing where order validation failed
    # TODO - print reason for validation fail
    def place_order(self, market, order) -> None:
        runner_context = self.get_runner_context(*order.lookup)
        if self.validate_order(runner_context, order):
            runner_context.place()
            market.place_order(order)
        else:
            active_logger.warning(f'order validation failed for "{order.selection_id}"')


class BackTestClientNoMin(clients.BacktestClient):
    """
    flumine back test client with no minimum bet size
    """
    @property
    def min_bet_size(self) -> Optional[float]:
        return 0


class MyFeatureData:
    """
    track feature data for runners in one market

    store:
    - window instances
    - dictionary of features indexed by runner ID, then indexed by feature name
    - list of market books to be passed to features
    """
    def __init__(self, market_book: MarketBook, features_config: dict):
        self.windows: bfw.Windows = bfw.Windows()
        self.features: Dict[int, Dict[str, bff.RunnerFeatureBase]] = {
            runner.selection_id: bff.generate_features(
                runner.selection_id,
                market_book,
                self.windows,
                features_config
            ) for runner in market_book.runners
        }
        self.market_books: List[MarketBook] = []


class MyFeatureStrategy(MyBaseStrategy):
    """
    Store feature data for each market, providing functionality for updating features when new market_book received
    By default features configuration is left blank so default features are used for each runner, but this can be
    overridden
    """

    # number of seconds before start that trading is stopped and greened up
    cutoff_seconds = 2

    # seconds before race start trading allowed
    pre_seconds = 180

    # feature configuration dict (use defaults)
    features_config = bff.get_default_features_config()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # feature data, indexed by market ID
        self.feature_data: [Dict, MyFeatureData] = dict()

        # create edge detection for cutoff and trading allowed
        self.cutoff = EdgeDetector(False)
        self.allow = EdgeDetector(False)

    def create_feature_data(self, market: Market, market_book: MarketBook) -> MyFeatureData:
        """
        create a `MyFeatureData` instance to track runner features for one market
        (can be overridden to customise features)
        """
        return MyFeatureData(market_book, self.features_config)

    def market_initialisation(self, market: Market, market_book: MarketBook, feature_data: MyFeatureData):
        """
        called first time strategy receives a new market
        blank function to be overridden with customisations for market initialisations
        """
        pass

    def do_feature_processing(self, feature_data: MyFeatureData, market_book: MarketBook):
        """
        update each feature for each runner for a new market book
        N.B. market_book MUST have been added to feature_data.market_books prior to calling this function
        """
        # loop runners
        for runner_index, runner in enumerate(market_book.runners):

            # process each feature for current runner
            for feature in feature_data.features[runner.selection_id].values():
                feature.process_runner(
                    feature_data.market_books,
                    market_book,
                    feature_data.windows,
                    runner_index
                )

    def process_get_feature_data(self, market: Market, market_book: MarketBook) -> MyFeatureData:
        """
        get runner feature data for current market with new `market_book` received
        - if first time market is received then `market_initialisation()` is called
        """

        # check if market has been initialised
        if market.market_id not in self.feature_data:
            feature_data = self.create_feature_data(market, market_book)
            self.feature_data[market.market_id] = feature_data
            self.market_initialisation(market, market_book, feature_data)

        # get feature data instance for current market
        feature_data = self.feature_data[market.market_id]

        # if runner doesnt have an element in features dict then add (this must be done before window processing!)
        for runner in market_book.runners:
            if runner.selection_id not in feature_data.features:

                runner_features = bff.generate_features(
                    selection_id=runner.selection_id,
                    book=market_book,
                    windows=feature_data.windows,
                    features_config=self.features_config
                )

                feature_data.features[runner.selection_id] = runner_features

        # append new market book to list
        feature_data.market_books.append(market_book)

        # update windows
        feature_data.windows.update_windows(feature_data.market_books, market_book)

        # process features
        self.do_feature_processing(feature_data, market_book)

        return feature_data

    def update_cutoff(self, market_book: MarketBook):
        """update `cutoff`, denoting whether trading is cutoff (too close to start) based on market book timestamp"""
        self.cutoff.update(market_book.publish_time >=
                           (market_book.market_definition.market_time - timedelta(seconds=self.cutoff_seconds)))

    def update_allow(self, market_book: MarketBook):
        """update `allow`, denoting if close enough to start of race based on market book timestamp"""
        self.allow.update(market_book.publish_time >=
                            (market_book.market_definition.market_time - timedelta(seconds=self.pre_seconds)))
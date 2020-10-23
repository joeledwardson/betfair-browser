from typing import Dict, List

from betfairlightweight.resources import MarketBook

from mytrading.feature import window as bfw, feature as bff


class FeatureHolder:
    """
    track feature data for runners in one market

    store:
    - window instances
    - dictionary of features indexed by runner ID, then indexed by feature name {runner ID: {feature name: feature}}
    - list of market books to be passed to features
    """
    def __init__(self):
        self.windows: bfw.Windows = bfw.Windows()
        self.features: Dict[int, Dict[str, bff.RunnerFeatureBase]] = dict()
        self.market_books: List[MarketBook] = []

    def process_market_book(self, market_book: MarketBook):
        """
        update each feature for each runner for a new market book
        N.B. market_book MUST have been added to feature_data.market_books prior to calling this function
        """
        # loop runners
        for runner_index, runner in enumerate(market_book.runners):

            # process each feature for current runner
            for feature in self.features[runner.selection_id].values():
                feature.process_runner(
                    self.market_books,
                    market_book,
                    self.windows,
                    runner_index
                )
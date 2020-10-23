from __future__ import annotations
from betfairlightweight.resources.streamingresources import MarketDefinition
from betfairlightweight.resources.bettingresources import MarketCatalogue, MarketBook
from mytrading.process.times import event_time
from mytrading.process.names import get_names


class MarketInfo:
    def __init__(self):
        self.event_name = ''
        self.market_time = None
        self.market_type = ''
        self.names = {}
        self.catalogue: MarketCatalogue = None
        self.market_def: MarketDefinition = None

    @classmethod
    def from_historical(cls, market_definition: MarketDefinition) -> MarketInfo:
        instance = cls()

        instance.event_name = market_definition.event_name
        instance.market_time = market_definition.market_time
        instance.market_type = market_definition.market_type
        instance.names = get_names(market_definition)
        instance.market_def = market_definition

        return instance

    @classmethod
    def from_catalogue(cls, catalogue: MarketCatalogue) -> MarketInfo:
        instance = cls()

        instance.event_name = catalogue.event.name
        instance.market_time = catalogue.market_start_time
        instance.market_type = catalogue.description.market_type if catalogue.description else ''
        instance.names = get_names(catalogue, name_attr='runner_name')
        instance.catalogue = catalogue

        return instance

    def __repr__(self):
        market_time = event_time(self.market_time, localise=False) if self.market_time else ''
        return f'{self.event_name} {market_time} {self.market_type}'


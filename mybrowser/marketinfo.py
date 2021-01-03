from __future__ import annotations
from betfairlightweight.resources.streamingresources import MarketDefinition
from betfairlightweight.resources.bettingresources import MarketCatalogue, MarketBook
from typing import Dict

from mytrading.process import times as processtimes
from mytrading.process import names as processnames


class MarketInfo:
    def __init__(self):
        self.event_name = ''
        self.market_time = None
        self.market_type = ''
        self.names = {}
        self.catalogue: MarketCatalogue = None
        self.market_def: MarketDefinition = None

        # market ID
        self.market_id = ''

    @classmethod
    def from_historical(cls, market_definition: MarketDefinition, first_record: MarketBook) -> MarketInfo:
        instance = cls()

        instance.event_name = market_definition.event_name
        instance.market_time = market_definition.market_time
        instance.market_type = market_definition.market_type
        instance.names = processnames.get_names(market_definition)
        instance.market_id = first_record.market_id

        # set historical market definition instance
        instance.market_def = market_definition

        return instance

    @classmethod
    def from_catalogue(cls, catalogue: MarketCatalogue) -> MarketInfo:
        instance = cls()

        instance.event_name = catalogue.event.name
        instance.market_time = catalogue.market_start_time
        instance.market_type = catalogue.description.market_type if catalogue.description else ''
        instance.names = processnames.get_names(catalogue, name_attr='runner_name')
        instance.market_id = catalogue.market_id

        # set catalogue instance
        instance.catalogue = catalogue

        return instance

    def clear(self):
        self.event_name = ''
        self.market_time = None
        self.market_type = ''
        self.names = {}
        self.catalogue: MarketCatalogue = None
        self.market_def: MarketDefinition = None
        self.market_id = ''

    def __repr__(self):
        market_time = processtimes.event_time(self.market_time, localise=False) if self.market_time else ''
        return f'{self.event_name} {market_time} {self.market_type} "{self.market_id}"'


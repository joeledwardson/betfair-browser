from __future__ import annotations
import copy
from datetime import datetime, timedelta
from typing import Dict, List
import logging
import numpy as np
import pandas as pd
from betfairlightweight.resources import MarketBook
from myutils import timing
# from collections import MutableMapping
from .features import ftrs_reg, RFBase
from ...exceptions import FeatureException

active_logger = logging.getLogger(__name__)


class FeatureHolder(dict):
    """dictionary holder of (feature name => feature instance)"""
    @classmethod
    def generator(cls, configs: dict) -> FeatureHolder:
        """
        create dictionary of features based on a dictionary of `features_config`,
        - key: feature usage name
        - value: dict of
            - 'name': class name of feature
            - 'kwargs': dict of constructor arguments used when creating feature
        """
        ftrs = cls()
        configs = copy.deepcopy(configs)
        for i, (name, conf) in enumerate(configs.items()):
            active_logger.info(f'creating feature #{i}, name: "{name}')
            if type(conf) is not dict:
                raise FeatureException(f'feature config not dict: "{conf}"')
            if 'name' not in conf:
                raise FeatureException(f'feature does not have "name" attr')
            ftr_key = conf.pop('name')
            active_logger.info(f'generating feature of class "{ftr_key}"')
            feature_class: type(RFBase) = ftrs_reg[ftr_key]
            kwargs = conf.pop('kwargs', {})
            if type(kwargs) is not dict:
                raise FeatureException(f'feature kwargs not dict: {kwargs}')
            if conf:
                raise FeatureException(f'feature has config keys not recognised: "{conf}"')
            try:
                ftrs[name] = feature_class(**kwargs, ftr_identifier=name)
            except TypeError as e:
                raise FeatureException(f'error creating feature: {e}')
        return ftrs

    def max_cache(self) -> float:
        """get maximum number of seconds as delay from feature set for computations"""
        # inner function for recursion
        def _get_delay(dly, _ftrs):
            # loop features and sub-features, taking max caching seconds for each
            for ftr in _ftrs.values():
                dly = max(dly, ftr.cache_secs or 0)
                dly = _get_delay(dly, ftr.sub_features)
            return dly
        return _get_delay(0, self)

    def get_data(self) -> Dict[str, pd.Series]:
        """get feature data recursively into dictionary of pandas Series, indexed by feature identifier"""

        # loop features and get data recursively
        data = {}

        def inner(_features):
            for ftr in _features.values():
                if ftr.ftr_identifier in data:
                    raise FeatureException(f'feature "{ftr.ftr_identifier}" already exists')
                if len(ftr.out_cache):
                    a = np.array(ftr.out_cache)
                    data[ftr.ftr_identifier] = pd.Series(a[:, 1], a[:, 0])
                # call function recursively with sub features
                inner(ftr.sub_features)

        inner(self)
        return data

    def _stream(self, selection_id: int, records: List[List[MarketBook]]):
        """simulate streaming and process historical records with a set of features for a selected runner"""
        for bk in records:
            bk = bk[0]
            for i_rn, runner_book in enumerate(bk.runners):
                if runner_book.selection_id == selection_id:
                    for feature in self.values():
                        feature.process_runner(bk, i_rn)

    def simulate(
            self,
            hist_records: List[List[MarketBook]],
            selection_id: int,
            cmp_start: datetime,
            cmp_end: datetime,
            buffer_s: float
    ) -> Dict[str, pd.Series]:
        """for a historical market, generate runner features from config, simulate feature processing for market within
        computation start and end time (allowing for buffer seconds), and return dictionary of feature data"""

        # check record set empty
        if not hist_records:
            raise FeatureException(f'records set empty')
        active_logger.info(f'creating feature data from {len(hist_records)} records')

        # get computations start buffer seconds
        cache_s = self.max_cache()
        total_s = buffer_s + cache_s
        active_logger.info(f'using buffer of {buffer_s}s + cache of {cache_s}s before start for computations')

        # trim records to within computation windows
        modified_start = cmp_start - timedelta(seconds=total_s)
        hist_records = [r for r in hist_records if modified_start <= r[0].publish_time <= cmp_end]
        active_logger.info(f'{cmp_start} is specified start time')
        active_logger.info(f'{modified_start} is adjusted for buffer computation start time')
        active_logger.info(f'{cmp_end} is computation end time')

        # check trimmed record set not empty
        if not len(hist_records):
            raise FeatureException(f'trimmed record set empty')
        active_logger.info(f'trimmed record set has {len(hist_records)} records')

        # initialise features with first of trimmed books, then simulate market stream and process feature updates
        for feature in self.values():
            feature.race_initializer(selection_id, hist_records[0][0])
        self._stream(selection_id, hist_records)

        # get feature data from feature set
        return self.get_data()

    def __getitem__(self, item) -> RFBase:
        return super().__getitem__(item)


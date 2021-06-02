from __future__ import annotations
from betfairlightweight.resources.bettingresources import MarketBook
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging
from collections import deque
import statistics

from mytrading.exceptions import FeatureException
from mytrading.process import get_best_price, closest_tick, tick_spread, traded_runner_vol, get_record_tv_diff
from mytrading.process.ticks import LTICKS_DECODED
from myutils import mytiming, myregistrar, mydict


ftrs_reg = myregistrar.MyRegistrar()
active_logger = logging.getLogger(__name__)

SUB_FEATURE_CONFIG_SPEC = {
    'name': {
        'type': str,
    },
    'kwargs': {
        'type': dict,
        'optional': True,
    }
}


class RFBase:
    """
    base class for runner features that can hold child features specified by `sub_features_config`, dictionary of
    (child feature identifier => child feature constructor kwargs)
    """
    def __init__(
            self,
            sub_features_config: Optional[Dict] = None,
            parent: Optional[RFBase] = None,
            ftr_identifier=None,
            cache_count=2,
            cache_secs=None,
            cache_insidewindow=None,
    ):
        """by default store cache of 2 values using `cache_count`. If cache seconds `cache_secs` is specified this
        takes priority over `cache_count` by indicating number of seconds prior to cache values. In this case,
        `cache_insidewindow` determines whether first cache value in queue should be inside the time window or
        outside"""

        self.parent = parent
        self.selection_id: int = None
        if ftr_identifier:
            self.ftr_identifier = ftr_identifier
        else:
            self.ftr_identifier = self.__class__.__name__
        if self.parent:
            self.ftr_identifier = '.'.join([
                self.parent.ftr_identifier,
                self.ftr_identifier
            ])

        self._values_cache = deque()
        self.out_cache = deque()
        self.cache_count = cache_count
        self.cache_secs = cache_secs
        self.inside_window = cache_insidewindow

        self.sub_features: Dict[str, RFBase] = {}
        if sub_features_config:
            if type(sub_features_config) is not dict:
                raise FeatureException(
                    f'error in feature "{self.ftr_identifier}", sub features config is not dict'
                )
            for sub_nm, sub_cfg in sub_features_config.items():
                if type(sub_cfg) is not dict:
                    raise FeatureException(
                        f'error in feature "{self.ftr_identifier}", sub-feature "{sub_nm}" value is not dict'
                    )
                mydict.validate_config(sub_cfg, SUB_FEATURE_CONFIG_SPEC)
                feature_class = ftrs_reg[sub_cfg['name']]
                feature_kwargs = sub_cfg.get('kwargs', {})
                try:
                    self.sub_features[sub_nm] = feature_class(
                        parent=self,
                        **feature_kwargs,
                        ftr_identifier=sub_nm,  # use dictionary name as feature name
                    )
                except TypeError as e:
                    raise FeatureException(
                        f'error in feature "{self.ftr_identifier}", sub-feature "{sub_nm}": {e}'
                    )
        self._user_data = None

    def update_user_data(self, user_data):
        self._user_data = user_data
        for ftr in self.sub_features.values():
            ftr.update_user_data(user_data)

    def _update_cache(self):
        if self.cache_secs:
            if len(self._values_cache):
                dt = self._values_cache[-1][0]
                dtw = dt - timedelta(seconds=self.cache_secs)
                idx = 0 if self.inside_window else 1
                while len(self._values_cache) > idx:
                    if self._values_cache[idx][0] >= dtw:
                        break
                    else:
                        self._values_cache.popleft()
        else:
            while len(self._values_cache) > self.cache_count:
                self._values_cache.popleft()

    def race_initializer(self, selection_id: int, first_book: MarketBook) -> None:
        """initialize feature with first market book of race and selected runner"""
        self.selection_id = selection_id
        for sub_feature in self.sub_features.values():
            sub_feature.race_initializer(selection_id, first_book)

    def _publish_update(self, new_book, runner_index, pt=None):
        # get feature value, ignore if None
        value = self._get_value(new_book, runner_index)
        if value is None:
            return

        # if publish time not explicitly passed, use parent if exist else market book
        if pt is None:
            if self.parent is None:
                pt = new_book.publish_time
            else:
                pt = self.parent._values_cache[-1][0]

        self._values_cache.append((pt, value))
        self.out_cache.append((pt, value))
        self._update_cache()

        for sub_feature in self.sub_features.values():
            sub_feature.process_runner(new_book, runner_index)

    @mytiming.timing_register_attr(name_attr='ftr_identifier')
    def process_runner(self, new_book: MarketBook, runner_index) -> None:
        """update feature value and add to cache"""
        self._publish_update(new_book, runner_index)

    def _get_value(self, new_book: MarketBook, runner_index) -> Optional[Any]:
        """
        implement this function to return feature value from new market book received
        return None if do not want value to be stored
        """
        raise NotImplementedError

    def last_value(self) -> Optional[Any]:
        """get most recent value processed, if empty return None"""
        return self._values_cache[-1][1] if len(self._values_cache) else None


@ftrs_reg.register_element
class RFChild(RFBase):
    """
    feature that must be used as a sub-feature to existing feature
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if kwargs.get('parent') is None:
            raise FeatureException(f'sub-feature has not received "parent" argument')

    def _get_value(self, new_book: MarketBook, runner_index):
        return self.parent.last_value()


@ftrs_reg.register_element
class RFMvAvg(RFChild):
    """moving average of parent values"""
    def _get_value(self, new_book: MarketBook, runner_index):
        if len(self.parent._values_cache):
            return statistics.mean([v[1] for v in self.parent._values_cache])


@ftrs_reg.register_element
class RFSample(RFChild):
    """sample values to periodic timestamps with most recent value"""
    def __init__(self, periodic_ms, **kwargs):
        super().__init__(**kwargs)
        self.periodic_ms = periodic_ms
        self.last_timestamp: datetime = None

    def race_initializer(self, selection_id: int, first_book: MarketBook):
        super().race_initializer(selection_id, first_book)
        self.last_timestamp = first_book.publish_time.replace(microsecond=0)

    def process_runner(self, new_book: MarketBook, runner_index):
        # if data is sampled and more than one sample time has elapsed, fill forwards until time is met
        while int((new_book.publish_time - self.last_timestamp).total_seconds() * 1000) > self.periodic_ms:
            self.last_timestamp = self.last_timestamp + timedelta(milliseconds=self.periodic_ms)
            self._publish_update(new_book, runner_index, self.last_timestamp)


@ftrs_reg.register_element
class RFTVLad(RFBase):
    """traded volume ladder"""
    def _get_value(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].ex.traded_volume or None


@ftrs_reg.register_element
class RFTVLadDif(RFChild):
    """child feature of `RFTVLad`, computes difference in parent current traded volume ladder and first in cache"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if type(self.parent) is not RFTVLad:
            raise FeatureException('expected traded vol feature parent')

    def _get_value(self, new_book: MarketBook, runner_index):
        if len(self.parent._values_cache) >= 2:
            return get_record_tv_diff(
                self.parent._values_cache[-1][1],
                self.parent._values_cache[0][1]
            )
        else:
            return None


class _RFTVLadDifFunc(RFChild):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if type(self.parent) is not RFTVLadDif:
            raise FeatureException('expected traded vol diff feature parent')

    def _get_value(self, new_book: MarketBook, runner_index):
        if len(self.parent._values_cache):
            tvs = self.parent._values_cache[-1][1]
            if len(tvs):
                return self.lad_func(tvs)
        return None

    def lad_func(self, tvs):
        raise NotImplementedError


@ftrs_reg.register_element
class RFTVLadMax(_RFTVLadDifFunc):
    """maximum of traded volume difference ladder over cached values"""
    def lad_func(self, tvs):
        v = max([x['price'] for x in tvs])
        return v


@ftrs_reg.register_element
class RFTVLadMin(_RFTVLadDifFunc):
    """minimum of traded volume difference ladder over cached values"""
    def lad_func(self, tvs):
        v = min([x['price'] for x in tvs])
        return v


@ftrs_reg.register_element
class RFTVLadSpread(_RFTVLadDifFunc):
    """tick spread between min/max of traded vol difference"""
    def lad_func(self, tvs):
        v_max = max([x['price'] for x in tvs])
        v_min = min([x['price'] for x in tvs])
        return tick_spread(v_min, v_max, check_values=False)


@ftrs_reg.register_element
class RFTVLadTot(_RFTVLadDifFunc):
    """total new traded volume money"""
    def lad_func(self, tvs):
        v = sum([x['size'] for x in tvs])
        return v


@ftrs_reg.register_element
class RFBkSplit(RFBase):
    """
    traded volume since previous update that is above current best back price
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_best_back = None
        self.previous_best_lay = None
        self.previous_ladder = dict()

    def _get_value(self, new_book: MarketBook, runner_index):

        runner = new_book.runners[runner_index]
        value = None

        if self.previous_best_back and self.previous_best_lay:
            diff = get_record_tv_diff(
                runner.ex.traded_volume,
                self.previous_ladder
            )
            # difference in new back and lay money
            back_diff = sum([x['size'] for x in diff if x['price'] <= self.previous_best_back])
            lay_diff = sum([x['size'] for x in diff if x['price'] >= self.previous_best_lay])
            value = back_diff - lay_diff

        # update previous state values
        self.previous_best_back = get_best_price(runner.ex.available_to_back)
        self.previous_best_lay = get_best_price(runner.ex.available_to_lay)
        self.previous_ladder = runner.ex.traded_volume

        return value


@ftrs_reg.register_element
class RFLTP(RFBase):
    """Last traded price of runner"""
    def _get_value(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].last_price_traded


@ftrs_reg.register_element
class RFWOM(RFBase):
    """
    Weight of money (difference of available-to-lay to available-to-back)
    applied to `wom_ticks` number of ticks on BACK and LAY sides of the book
    """
    def __init__(self, wom_ticks, **kwargs):
        super().__init__(**kwargs)
        self.wom_ticks = wom_ticks

    def _get_value(self, new_book: MarketBook, runner_index):
        atl = new_book.runners[runner_index].ex.available_to_lay
        atb = new_book.runners[runner_index].ex.available_to_back

        if atl and atb:
            back = sum([x['size'] for x in atb[:self.wom_ticks]])
            lay = sum([x['size'] for x in atl[:self.wom_ticks]])
            return lay - back
        else:
            return None


@ftrs_reg.register_element
class RFBck(RFBase):
    """Best available back price of runner"""
    def _get_value(self, new_book: MarketBook, runner_index):
        return get_best_price(new_book.runners[runner_index].ex.available_to_back)


@ftrs_reg.register_element
class RFLay(RFBase):
    """
    Best available lay price of runner
    """
    def _get_value(self, new_book: MarketBook, runner_index):
        return get_best_price(new_book.runners[runner_index].ex.available_to_lay)


@ftrs_reg.register_element
class RFLadSprd(RFBase):
    """
    tick spread between best lay and best back - defaults to 1000 if cannot find best back or lay
    """
    def _get_value(self, new_book: MarketBook, runner_index):
        best_lay = get_best_price(new_book.runners[runner_index].ex.available_to_lay)
        best_back = get_best_price(new_book.runners[runner_index].ex.available_to_back)
        if best_lay and best_back:
            return tick_spread(best_back, best_lay, check_values=False)
        else:
            return len(LTICKS_DECODED)


@ftrs_reg.register_element
class RFLadBck(RFBase):
    """
    best available price-sizes on back side within specified number of elements of best price
    """
    def __init__(self, n_elements, *args, **kwargs):
        self.n_elements = n_elements
        super().__init__(*args, **kwargs)

    def _get_value(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].ex.available_to_back[:self.n_elements]


@ftrs_reg.register_element
class RFLadLay(RFBase):
    """
    best available price-sizes on lay side within specified number of elements of best price
    """
    def __init__(self, n_elements, *args, **kwargs):
        self.n_elements = n_elements
        super().__init__(*args, **kwargs)

    def _get_value(self, new_book: MarketBook, runner_index):
        return new_book.runners[runner_index].ex.available_to_lay[:self.n_elements]


@ftrs_reg.register_element
class RFMaxDif(RFChild):
    """maximum difference of parent cache values"""
    def _get_value(self, new_book: MarketBook, runner_index):
        if len(self.parent._values_cache) >= 2:
            return max(abs(np.diff([v[1] for v in self.parent._values_cache])).tolist())
        else:
            return 0


@ftrs_reg.register_element
class RFTVTot(RFBase):
    """total traded volume of runner"""
    def _get_value(self, new_book: MarketBook, runner_index):
        return traded_runner_vol(new_book.runners[runner_index])


@ftrs_reg.register_element
class RFIncSum(RFChild):
    """incrementally sum parent values"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sum = 0

    def _get_value(self, new_book: MarketBook, runner_index):
        self._sum += self.parent._values_cache[-1][1]
        return self._sum


@ftrs_reg.register_element
class RFSum(RFChild):
    """sum parent cache values"""
    def _get_value(self, new_book: MarketBook, runner_index):
        return sum(v[1] for v in self.parent._values_cache)


@ftrs_reg.register_element
class RFTick(RFChild):
    """convert parent to tick value"""
    def _get_value(self, new_book: MarketBook, runner_index):
        return closest_tick(self.parent._values_cache[-1][1], return_index=True)


@ftrs_reg.register_element
class RFDif(RFChild):
    """compare parent most recent value to first value in cache"""
    def _get_value(self, new_book: MarketBook, runner_index):
        return self.parent._values_cache[-1][1] - self.parent._values_cache[0][1]


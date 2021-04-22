from typing import List, Dict

from betfairlightweight.resources import MarketBook

from .features import RFBase
from .window import Windows
from myutils import mytiming


@mytiming.timing_register
def hist_runner_features(
        selection_id: int,
        records: List[List[MarketBook]],
        windows: Windows,
        features: Dict[str, RFBase]):
    """
    process historical records with a set of features for a selected runner
    """
    feature_records = []
    for i in range(len(records)):
        new_book = records[i][0]
        feature_records.append(new_book)
        windows.update_windows(feature_records, new_book)

        runner_index = next((i for i, r in enumerate(new_book.runners) if r.selection_id == selection_id), None)
        if runner_index is not None:
            for feature in features.values():
                feature.process_runner(new_book, runner_index)

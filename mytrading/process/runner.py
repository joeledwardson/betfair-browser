from typing import Union, List

from betfairlightweight.resources import MarketDefinitionRunner
from betfairlightweight.resources.bettingresources import RunnerBook


def get_book(runners: Union[List[RunnerBook], List[MarketDefinitionRunner]], selection_id) -> RunnerBook:
    """
    Get a runner object by checking for match of "selection_id" attribute from a list of objects
    """
    for runner in runners:
        if selection_id == runner.selection_id:
            return runner
    else:
        return None
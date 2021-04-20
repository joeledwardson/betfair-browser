import re
from typing import List, Dict, Optional, Union
import logging


active_logger = logging.getLogger(__name__)


def get_names(market, name_attr='name', name_key=False) -> Dict[int, str]:
    """
    Get dictionary of {runner ID: runner name} from a market definition
    - name_attr: optional attribute name to retrieve runner name
    - name_key: optional flag to return {runner name: runner ID} with name as key instead
    """
    if not name_key:
        return {
            runner.selection_id: getattr(runner, name_attr)
            for runner in market.runners
        }
    else:
        return {
            getattr(runner, name_attr): runner.selection_id
            for runner in market.runners
        }


# TODO - if this is specific to oddschecker then should be in oddschecker file?
def name_processor(name):
    """remove all characters not in alphabet and convert to lower case for horse names"""
    return re.sub('[^a-zA-Z]', '', name).lower()


# TODO - specific to oddschecker?
def names_to_id(input_names: List[str], name_id_map: Dict) -> List:
    """
    Convert a list of runner names to betfair IDs using the 'name_id_map' dict, mapping betfair IDs to betfair runner
    names
    """

    input_names = [name_processor(n) for n in input_names]
    name_id_map = {name_processor(k):v for (k,v) in name_id_map.items()}
    names = list(name_id_map.keys())
    if not all([n in names for n in input_names]):
        active_logger.warning(f'input names "{input_names}" do not match with mapping names "{names}"')
        return None
    if len(input_names) > len(set(input_names)):
        active_logger.warning(f'input names "{input_names}" are not all unique"')
        return None
    if len(names) > len(set(names)):
        active_logger.warning(f'mapping names "{names}" are not all unique"')
    return [name_id_map[n] for n in input_names]


def market_id_processor(market_id):
    """remove 1. prefix used in some betfair IDs"""
    return re.sub(r'^1.', '', market_id)


from os import path
import re
from ..utils.storage import RE_MARKET_ID
from ..utils.storage import get_hist_marketdef, search_recorded_cat
from ..utils.storage import walk_first


def get_event_dir_info(dir_path) -> str:
    """
    get event information string containing venue from a directory path
    directory path can be either:
    - betfair historical event dir path containing market files, where event info contained in files
    - recorded event dir, where market dirs hold catalogue file for event info

    on failure to extract info from both above, returns empty string
    """
    _, dirs, files = walk_first(dir_path)

    for f in files:
        # if historical, market streaming contained in files using market ID as name
        if re.match(RE_MARKET_ID, f):
            market_def = get_hist_marketdef(path.join(dir_path, f))
            if market_def:
                return market_def.event_name

    for d in dirs:
        # if recorded, event dir holds dirs named using market IDs which contain catalogue file
        if re.match(RE_MARKET_ID, d):
            sub_dir_path = path.join(dir_path, d)
            cat = search_recorded_cat(sub_dir_path)
            if cat:
                return cat.event.name

    return ''

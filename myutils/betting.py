import re
from queue import Queue
import betfairlightweight
from betfairlightweight.resources.bettingresources import PriceSize, RunnerBook, MarketBook
from betfairlightweight.resources.streamingresources import MarketDefinition, MarketDefinitionRunner
import os
import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Optional, Union
from datetime import datetime
from myutils import generic, timing
import keyring
import json

active_logger = logging.getLogger(__name__)

# Change this certs path to wherever you're storing your certificates
certs_path = os.environ['USERPROFILE'] + r'\OneDrive\Betfair\bf certs'

my_username = keyring.get_password('bf_username', 'joel')
my_password = keyring.get_password('bf_password', 'joel')
my_app_key  = keyring.get_password('bf_app_key',  'joel')


def get_api_client() -> betfairlightweight.APIClient:
    """Get Betfair API client with credentials"""
    return betfairlightweight.APIClient(username=my_username,
                                        password=my_password,
                                        app_key=my_app_key,
                                        certs=certs_path)


def _construct_hist_dir(event_dt: datetime, event_id, market_id) -> str:
    """get path conforming to betfair historical data standards for a given event datetime, event ID, and market ID"""

    # cant use %d from strftime as it 0-pads and betfair doesnt
    return os.path.join(
        event_dt.strftime('%Y\\%b'),
        str(event_dt.day),
        str(event_id),
        str(market_id)
    )


def construct_hist_dir(market_book: MarketBook):
    """get path conforming to betfair historical data standards for a given market book"""
    market_id = market_book.market_id
    event_id = market_book.market_definition.event_id
    event_dt = market_book.market_definition.market_time

    return _construct_hist_dir(event_dt, event_id, market_id)



def get_market_info(file_path: str, market_attrs: List[str]) -> dict:
    """
    Get information about a Betfair historical/streaming file by reading the first line of contents
    market definition attributes are read as specified by `market_attrs`

    N.B. attribute must be specified in raw Betfair form rather than pythonic, i.e. 'marketTime' rather than
    'market_time'
    """
    with open(file_path) as f:
        dat = json.loads(f.readline())
    try:
        return {
            k: dat['mc'][0]['marketDefinition'].get(k)
            for k in market_attrs
        }
    except KeyError as e:
        return {}


def get_historical(api_client : betfairlightweight.APIClient, directory) -> Queue:
    """Get Queue object from historical Betfair data file"""

    output_queue = Queue()

    # stop it winging about stream latency
    stream_logger = logging.getLogger('betfairlightweight.streaming.stream')
    level = stream_logger.level
    stream_logger.setLevel(logging.CRITICAL)

    listener = betfairlightweight.StreamListener(output_queue=output_queue)
    stream = api_client.streaming.create_historical_stream(
        file_path=directory,
        listener=listener
    )
    stream.start()

    # reset to original level
    stream_logger.setLevel(level)

    return output_queue


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


def closest_tick(value: float, return_index=False) -> float:
    """
    Convert an value to the nearest odds tick, e.g. 2.10000001 would be converted to 2.1
    Specify return_index=True to get index instead of value
    """
    return generic.closest_value(TICKS_DECODED, value, return_index)


def event_time(dt: datetime) -> str:
    """
    Time of event in HH:MM, converted from betfair UTC to local
    """
    return timing.localise(dt).strftime("%H:%M")


def bf_dt(dt: datetime) -> str:
    """Datetime format to use with betfair API"""
    return dt.strftime("%Y-%m-%dT%TZ")


def pre_off(record_list, start_time: datetime) -> List[List[MarketBook]]:
    """Get historical records before the market start time"""
    return [r for r in record_list if r[0].publish_time < start_time]


def pre_inplay(record_list) -> List[List[MarketBook]]:
    """Get records before match goes in play"""
    return [r for r in record_list if not r[0].market_definition.in_play]


def record_datetimes(records) -> List[datetime]:
    """Get a list of 'publish_time' timestamps from historical records"""
    return [r[0].publish_time for r in records]


def get_recent_records(record_list, span_m, start_time: datetime) -> List[List[MarketBook]]:
    """Get records that are within 'span_m' minutes of market starttime"""
    return [r for r in record_list if within_x_seconds(span_m * 60, r[0], start_time)]


def get_recent_records_s(record_list, span_s, start_time: datetime) -> List[List[MarketBook]]:
    """Get records that are within 'span_s' seconds of market starttime"""
    return [r for r in record_list if within_x_seconds(span_s, r[0], start_time)]


def within_x_seconds(x, record, start_time: datetime, time_attr='publish_time'):
    """Check if a record is within x minutes of start time"""
    return 0 <= (start_time - getattr(record, time_attr)).total_seconds() <= x


def runner_data(record_list, additional_columns=None, runner_filter=lambda r:True) -> pd.DataFrame:
    """
    get runner last-traded-prices and traded-volumes in a dataframe
    optional arg 'additional_columns' can be set to a dict containing:
    - key: name of column in output dataframe
    - value: function to perform on each RunnerBook
    """

    additional_columns = additional_columns or {}

    if not record_list:
        active_logger.warning('cannot get ltp and tv, record list is empty')
        return None
    else:
        df = pd.DataFrame([{
            'pt': rec[0].publish_time,
            'selection_id': runner.selection_id,
            'ltp': runner.last_price_traded,
            **{
                k: v(runner) for (k, v) in additional_columns.items()
            }
        } for rec in record_list for runner in rec[0].runners if runner_filter(runner)])
        df = df.set_index('pt')
        return df


def runner_table(record_list, atr=lambda r:r.last_price_traded):
    """Get runner data with selection ids as columns"""
    return pd.DataFrame(
        [{
            runner.selection_id: atr(runner) for runner in rec[0].runners
        } for rec in record_list],
        index = record_datetimes(record_list))


def traded_runner_vol(runner: RunnerBook, is_dict=True):
    """Get runner traded volume across all prices"""
    return sum(e['size'] if is_dict else e.size for e in runner.ex.traded_volume)


def total_traded_vol(record: MarketBook):
    """Get traded volume across all runners at all prices"""
    return sum(traded_runner_vol(runner) for runner in record.runners)


def get_record_tv_diff(tv1: List[PriceSize], tv0: List[PriceSize], is_dict=False) -> List[Dict]:
    """
    Get difference between traded volumes from one tv ladder to another
    use is_dict=False if `price` and `size` are object attributes, use is_dict=True if are dict keys
    """
    traded_diffs = []

    if is_dict:
        atr = dict.get
    else:
        atr = getattr

    # loop items in second traded volume ladder
    for y in tv1:

        # get elements in first traded volume ladder if prices matches
        m = [x for x in tv0 if atr(x, 'price') == atr(y, 'price')]

        # first element that matches
        n = next(iter(m), None)

        # get price difference, using 0 for other value if price doesn't exist
        size_diff = atr(y, 'size') - (atr(n, 'size') if m else 0)

        # only append if there is a difference
        if size_diff:
            traded_diffs.append({
                'price': atr(y, 'price'),
                'size': size_diff
            })

    return traded_diffs


def get_tv_diffs(records, runner_id, is_dict=False) -> pd.DataFrame:
    """
    Get traded volume differences for a selected runner between adjacent records
    DataFrame has record publish time index, 'price' column for odds and 'size' column for difference in sizes
    """

    dts = []
    diffs = []

    for i in range(1, len(records)):
        r1 = records[i][0]
        r0 = records[i - 1][0]

        r0_book = get_book(r0.runners, runner_id)
        r1_book = get_book(r1.runners, runner_id)

        if r0_book and r1_book:
            new_diffs = get_record_tv_diff(r1_book.ex.traded_volume,
                                           r0_book.ex.traded_volume,
                                           is_dict)

            # filter out entries with £0
            new_diffs = [d for d in new_diffs if d['size']]
            diffs += new_diffs
            dts += [r1.publish_time for _ in new_diffs]

    return pd.DataFrame(diffs, index=dts)


def get_book(runners: Union[List[RunnerBook], List[MarketDefinitionRunner]], selection_id) -> RunnerBook:
    """
    Get a runner object by checking for match of "selection_id" attribute from a list of objects
    """
    for runner in runners:
        if selection_id == runner.selection_id:
            return runner
    else:
        return None


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


def name_processor(name):
    """remove all characters not in alphabet and convert to lower case for horse names"""
    return re.sub('[^a-zA-Z]', '', name).lower()


def market_id_processor(market_id):
    """remove 1. prefix used in some betfair IDs"""
    return re.sub(r'^1.', '', market_id)


def best_price(available: List[Dict]) -> float:
    """get best price from available ladder of price sizes, returning None if empty"""
    return available[0]['price'] if available else None


def get_tick_increments() -> pd.DataFrame:
    """
    Get list of tick increments in encoded integer format
    Retrieves list of {'Start', 'Stop', 'Step'} objects from JSON file 'ticks.json'
    """

    # generate file path based on current directory and filename "ticks.json"
    # when a library is imported, it takes active script as current directory and file is stored locally so have to
    # work out file path based on current directory
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(cur_dir, "ticks.json")

    # return file as pandas DataFrame
    return pd.read_json(file_path)


def generate_ticks(tick_increments: pd.DataFrame) -> np.ndarray:
    """
    Generate numpy list of ticks from list of {'Start', 'Stop', 'Step'} objects
    Output list is complete: [1.00, 1.01, ..., 1000]
    """
    return np.concatenate([
        np.arange(row.Start, row.Stop, row.Step)
        for index, row in tick_increments.iterrows()
    ])


def float_encode(v):
    """
    Encode a floating point number to integer format with x1000 scale
    """
    return round(v*1000)


def int_decode(v):
    """decode an integer encoded x1000 scale number to floating point actual value"""
    return v/1000


# numpy array of Betfair ticks in integer encoded form
TICKS: np.ndarray = generate_ticks(get_tick_increments())

# list of Betfair ticks in integer encoded form
LTICKS = TICKS.tolist()

# numpy array of Betfair ticks in actual floating values
TICKS_DECODED: np.ndarray = int_decode(TICKS)

# list of Betfair ticks in actual floating values
LTICKS_DECODED = TICKS_DECODED.tolist()
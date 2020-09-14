import re
from queue import Queue
import betfairlightweight
from betfairlightweight.resources.bettingresources import PriceSize, RunnerBook, MarketBook
from betfairlightweight.resources.streamingresources import MarketDefinition
import os
import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Optional
from datetime import datetime
from myutils import generic, timing
import keyring

active_logger = logging.getLogger(__name__)

# Change this certs path to wherever you're storing your certificates
certs_path = os.environ['USERPROFILE'] + r'\OneDrive\Betfair\bf certs'

# TODO update these to retreieve from memory!
# Change these login details to your own
my_username = keyring.get_password('bf_username', 'joel')
my_password = keyring.get_password('bf_password', 'joel')
my_app_key  = keyring.get_password('bf_app_key',  'joel')


# login and get Betfair API client
def get_api_client() -> betfairlightweight.APIClient:
    return betfairlightweight.APIClient(username=my_username,
                                        password=my_password,
                                        app_key=my_app_key,
                                        certs=certs_path)


# get Queue object from historical Betfair data file
def get_historical(api_client : betfairlightweight.APIClient, directory) -> Queue:
    output_queue = Queue()

    listener = betfairlightweight.StreamListener(output_queue=output_queue)
    stream = api_client.streaming.create_historical_stream(
        file_path=directory,
        listener=listener
    )
    stream.start()

    return output_queue


# convert a list of runner names to betfair IDs using the 'name_id_map' dict, mapping betfair IDs to betfair runner names
def names_to_id(input_names: List[str], name_id_map: Dict) -> List:
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


# convert an value to the nearest odds tick, e.g. 2.10000001 would be converted to 2.1
def round_to_tick(value):
    return generic.closest_value(TICKS_DECODED, value)


# time of event in HH:MM, converted from betfair UTC to local
def event_time(datetime: datetime):
    return timing.localise(datetime).strftime("%H:%M")


# datetime format to use with betfair API
def bf_dt(dt: datetime):
    return dt.strftime("%Y-%m-%dT%TZ")


# get historical records before the market start time
def pre_off(record_list, start_time: datetime):
    return [r for r in record_list if r[0].publish_time < start_time]


# get records before match goes in play
def pre_inplay(record_list):
    return [r for r in record_list if not r[0].market_definition.in_play]


# get a list of 'publish_time' timestamps from historical records
def record_datetimes(records):
    return [r[0].publish_time for r in records]


# get records that are within 'span_m' minutes of market starttime
def get_recent_records(record_list, span_m, start_time: datetime):
    return [r for r in record_list if within_x_seconds(span_m * 60, r[0], start_time)]


# get records that are within 'span_s' seconds of market starttime
def get_recent_records_s(record_list, span_s, start_time: datetime):
    return [r for r in record_list if within_x_seconds(span_s, r[0], start_time)]


# check if a record is within x minutes of start time
def within_x_seconds(x, record, start_time: datetime, time_attr='publish_time'):
    return 0 <= (start_time - getattr(record, time_attr)).total_seconds() <= x


# get runner last-traded-prices and traded-volumes in a dataframe
# optional arg 'additional_columns' can be set to a dict containing:
# - key: name of column in output dataframe
# - value: function to perform on each RunnerBook
def runner_data(record_list, additional_columns={}) -> pd.DataFrame:
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
        } for rec in record_list for runner in rec[0].runners])
        df = df.set_index('pt')
        return df


# get runner traded volume across all prices
def traded_runner_vol(runner: RunnerBook, is_dict=True):
    return sum(e['size'] if is_dict else e.size for e in runner.ex.traded_volume)


# get traded volume across all runners at all prices
def total_traded_vol(record: MarketBook):
    return sum(traded_runner_vol(runner) for runner in record.runners)


# get difference between traded volumes from one tv ladder to another
def get_record_tv_diff(tv1: List[PriceSize], tv0: List[PriceSize], is_dict=False) -> List[Dict]:
    traded_diffs = []

    if is_dict:
        tv0 = [PriceSize(**x) for x in tv0]
        tv1 = [PriceSize(**x) for x in tv1]

    for y in tv1:
        m = [x for x in tv0 if x.price == y.price]
        n = next(iter(m), None)

        traded_diffs.append({
            'price': y.price,
            'size': y.size - (n.size if m else 0)
        })
    return traded_diffs


# get traded volume differences for a selected runner
# DataFrame has record publish time index, 'price' column for odds and 'size' column for difference in sizes
def get_tv_diffs(records, runner_id, is_dict=False) -> pd.DataFrame:
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


# get a runner object by checking for match of "selection_id" attribute from a list of objects. Of either
# - betfairlightweight.resources.bettingresources.MarketDefinitionRunner
# - betfairlightweight.resources.bettingresources.RunnerBook
# types
def get_book(runners, id):
    for runner in runners:
        if id == runner.selection_id:
            return runner
    else:
        return None


# get dictionary of {runner ID: runner name} from a market definition
# name_attr: optional attribute name to retrieve runner name
# name_key: optional flag to return {runner name: runner ID} with name as key instead
def get_names(market, name_attr='name', name_key=False) -> Dict[int, str]:
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

# remove all characters not in alphabet and convert to lower case for horse names
def name_processor(name):
    return re.sub('[^a-zA-Z]', '', name).lower()

# remove 1. prefix used in some betfair IDs
def market_id_processor(market_id):
    return re.sub(r'^1.', '', market_id)



# get list of tick increments in encoded integer format
# retrieves list of {'Start', 'Stop', 'Step'} objects from JSON file
def get_tick_increments() -> pd.DataFrame:

    # generate file path based on current directory and filename "ticks.json"
    # when a library is imported, it takes active script as current directory and file is stored locally so have to
    # work out file path based on current directory
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(cur_dir, "ticks.json")

    # return file as pandas DataFrame
    with open(file_path) as json_file:
        return pd.read_json(file_path)

# generate numpy list of ticks from list of {'Start', 'Stop', 'Step'} objects
# output list is complete: [1.00, 1.01, ..., 1000]
def generate_ticks(tick_increments: pd.DataFrame) -> np.ndarray:
    return np.concatenate([
        np.arange(row.Start, row.Stop, row.Step)
        for index, row in tick_increments.iterrows()
    ])

# encode a floating point number to integer format with x1000 scale
def float_encode(v):
    return round(v*1000)

# decode an integer encoded x1000 scale number to floating point actual value
def int_decode(v):
    return v/1000



# numpy array of Betfair ticks in integer encoded form
TICKS: np.ndarray = generate_ticks(get_tick_increments())

# list of Betfair ticks in integer encoded form
LTICKS = TICKS.tolist()

# numpy array of Betfair ticks in actual floating values
TICKS_DECODED: np.ndarray = int_decode(TICKS)

# list of Betfair ticks in actual floating values
LTICKS_DECODED = TICKS_DECODED.tolist()
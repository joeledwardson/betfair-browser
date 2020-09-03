import re
from queue import Queue
import betfairlightweight
from betfairlightweight.resources.bettingresources import PriceSize, RunnerBook, MarketBook
from betfairlightweight.resources.streamingresources import MarketDefinition
import os
import numpy as np
import pandas as pd
import logging
from typing import List, Dict
from datetime import datetime
from myutils import generic

active_logger = logging.getLogger(__name__)

# Change this certs path to wherever you're storing your certificates
certs_path = os.environ['USERPROFILE'] + r'\OneDrive\Betfair\bf certs'


# TODO update these to retreieve from memory!
# Change these login details to your own
my_username = "joelyboyrasta@live.co.uk"
my_password = "L0rdTr@d3r"
my_app_key = "TRmlfYWsYKq8IduH"

# datetime format to use with betfair API
def bf_dt(dt: datetime):
    return dt.strftime("%Y-%m-%dT%TZ")

# get records before match goes in play
def pre_match(record_list):
    return [r for r in record_list if not r[0].market_definition.in_play]


def runner_ltp_tv(record_list, runner_id):
    ltp = []
    tv = []
    dts = []
    for record in record_list:
        runner_index = generic.get_index(record[0].runners,
                                         lambda runner: runner.selection_id == runner_id)
        if runner_index:
            runner = record[0].runners[runner_index]
            dts.append(record[0].publish_time)
            ltp.append(runner.last_price_traded)
            tv.append(traded_runner_vol(runner))
    return pd.DataFrame({'ltp': ltp, 'tv': tv}, index=dts)


def record_datetimes(records):
    return [r[0].publish_time for r in records]


def get_recent_records(record_list, span_m):
    return [r for r in record_list
            if within_x_minutes(span_m, r[0], record_list[0][0]) and
            not r[0].market_definition.in_play]


def within_x_minutes(x, r: MarketBook, r0: MarketBook):
    td = r0.market_definition.market_time - r.publish_time
    return 0 <= td.total_seconds() <= x * 60


def traded_runner_vol(runner: RunnerBook):
    return sum(e.size for e in runner.ex.traded_volume)


def total_traded_vol(record: MarketBook):
    return sum(traded_runner_vol(runner) for runner in record.runners)


def get_record_tv_diff(tv1: List[PriceSize], tv0: List[PriceSize]):
    traded_diffs = []
    for y in tv1:
        m = [x for x in tv0 if x.price == y.price]
        n = next(iter(m), None)
        traded_diffs.append({
            'price': y.price,
            'size': y.size - (n.size if m else 0)
        })
    return traded_diffs


def get_tv_diffs(records, runner_id):
    dts = []
    diffs = []

    for i in range(1, len(records)):
        r1 = records[i][0]
        r0 = records[i - 1][0]

        r1_index = generic.get_index(r1.runners,
                                     lambda runner: runner.selection_id == runner_id)
        r0_index = generic.get_index(r0.runners,
                                     lambda runner: runner.selection_id == runner_id)

        if r1_index and r0_index:
            new_diffs = get_record_tv_diff(r1
                                           .runners[r1_index].ex.traded_volume,
                                           r0.runners[r0_index].ex.traded_volume)
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
def get_names(m: MarketDefinition, name_attr='name') -> Dict[int, str]:
    return {
        runner.selection_id: getattr(runner, name_attr)
        for runner in m.runners
    }


# get last-traded-prices from list of [Marketbook] objects and runner names {runner ID: runner name}
def get_ltps(historical_list) -> pd.DataFrame:

    if not len(historical_list):
        logging.warning('cannot get ltps from empty historical list')
        return pd.DataFrame()

    # get selection id and names from market definition
    names = get_names(historical_list[0][0].market_definition)

    # empty list of timestamps
    timestamps = []

    # list of ltp records
    ltps = []

    # loop records
    for e in historical_list:

        # dict to store ltps from record (indexed by name, not ID)
        record_ltps = {}

        # loop runner objects
        for r in e[0].runners:

            # check name found in list
            if not r.selection_id in names.keys():
                logging.warning(f'selection id "{r.selection_id}" not found from market definition')
                continue

            # check last price traded variable is not None and non-zero
            if r.last_price_traded:

                name = names[r.selection_id]
                record_ltps[name] = r.last_price_traded

        # only append to lists if ay least 1 of selection ltps is non-zero
        if record_ltps:

            ltps.append(record_ltps)

            # add record timestamp to timestamp list
            pt = e[0].publish_time
            timestamps.append(pt)

    # return DataFrame
    return pd.DataFrame(ltps, index=timestamps)

# remove all characters not in alphabet and convert to lower case for horse names
def name_processor(name):
    return re.sub('[^a-zA-Z]', '', name).lower()


# remove 1. prefix used in some betfair IDs
def market_id_processor(market_id):
    return re.sub(r'^1.', '', market_id)


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
TICKS = generate_ticks(get_tick_increments())

# list of Betfair ticks in integer encoded form
LTICKS = TICKS.tolist()

# list of Betfair ticks in actual floating values
TICKS_DECODED = int_decode(TICKS).tolist()

# names of (betfairlightweight.resources.bettingresources.RunnerBookEx) attributes containing list of
# (betfairlightweight.resources.bettingresources.PriceSize) objects
BOOK_ATTRS = ['available_to_back', 'available_to_lay', 'traded_volume']

class HistoricalProcessor:

    def __init__(self):

        self.i = 0
        self.runners_list = {}
        self.price_list = ''
        self.book_index = 0
        self.tick_count = 0
        self.data_count = 0

    def get_by_id(self, obj, record_index):

        # get runner ID
        runner_id = obj.selection_id

        # check ID exists
        if runner_id not in self.runners_list.keys():
            active_logger.warning(f'Index {record_index}, runner ID {runner_id} object {obj} not found')
            return None

        # get runner object
        return self.runners_list[runner_id]

    # convert list of PriceSize elements to fixed length numerical elements
    #  value is size and index is based on TICKS
    def get_odds_array(self, price_list: List[PriceSize], ticks: np.ndarray, nearest_tick=False) -> np.ndarray:

        # create list of 0s same length as ticks list
        a = np.zeros(ticks.shape[0], dtype=float)

        for p in price_list:

            # convert "price" (odds value) to encoded integer value
            t = float_encode(p.price)

            # check that price appears in ticks array and get indexes where it does
            indexes = np.where(ticks == t)[0]

            if indexes.shape[0]:

                # if index found matching a tick then set the £ value to that index
                a[indexes[0]] = p.size

            else:

                # if index not found print warning
                book = BOOK_ATTRS[self.book_index]
                active_logger.debug(f'At index {self.i}, book {book}, price {p.price} not found in ticks')

        return a

    # process historical data into dict:
    # key = runner ID, value is 3d array with
    #   dim 0: record index (time)
    #   dim 1: tick index (1.00, 1.01, ... 1000)
    #   dim 2: data type [available to back, available to lay, traded volume]
    # params:
    #   historical_list: list of MarketBook elements
    #   ticks: array of tick odds (1.00, 1.01, 1.02, ... 1000)
    def process_runners(self, historical_list: List, ticks: np.ndarray) -> pd.DataFrame:

        self.data_count = len(historical_list)
        self.tick_count = len(ticks)

        record_timestamps = []
        runner_ids = None

        # loop records
        for self.i, record in enumerate(historical_list):

            # json always has data contained within first element
            record = record[0]

            # get timestamp
            record_timestamps.append(record.publish_time)

            if self.i == 0:

                # first record - loop runners in market (definition) and create blank arrays to store data
                self.runners_list = {
                    r.selection_id: {
                        'ladder': {
                            a: np.zeros([self.data_count, self.tick_count])
                            for a in BOOK_ATTRS
                        },
                        'last_price_traded': np.zeros((self.data_count, )), # allow for blanks
                        'market_def': [None] * self.data_count,
                        'book': [None] * self.data_count
                    } for r in record.market_definition.runners
                }

            # loop runners in market (definition)
            for market_def in record.market_definition.runners:

                runner = self.get_by_id(market_def, self.i)
                if not runner:
                    continue

                runner['market_def'][self.i] = market_def

            # loop runners in market (data)
            for book in record.runners:

                runner = self.get_by_id(book, self.i)
                if not runner:
                    continue

                # set last price traded
                runner['last_price_traded'][self.i] = book.last_price_traded

                # assign book object toy
                runner['book'][self.i] = book

                # get atb, atl and tv book instances
                price_lists = {
                    a: getattr(book.ex, a)
                    for a in BOOK_ATTRS
                }

                for book_attr, price_list in price_lists.items():

                    # get array of (tick count) length with price sizes
                    tick_prices = self.get_odds_array(price_list, ticks)

                    # assign to: current record (dim 0), current book (dim 2)
                    runner['ladder'][book_attr][self.i] = tick_prices

        # indexing hierarchy - first is timestamp, second is price
        index = pd.MultiIndex.from_product([record_timestamps, TICKS], names=['timestamp', 'price'])

        # columns hierarchy - first is runner ID, second is book attribute
        runner_ids = [k for k in self.runners_list]
        columns = pd.MultiIndex.from_product([runner_ids, BOOK_ATTRS], names=['runner_id', 'book_attribute'])

        # get data
        # each attribute (atb, atl, tv) must be flatten from [time, price] to a single axis
        # the produced array has entries of book attributes by time, that is, axis 0 is runner/attribute and axis 1 is time
        # thus, it must be transposed so that axis 0 is time and axis 1 is runner/attribute
        data = np.transpose(
            np.array([
                r['ladder'][a].flatten()
                for r in self.runners_list.values()
                for a in BOOK_ATTRS
            ])
        )

        return pd.DataFrame(
            data=data,
            index=index,
            columns=columns,
        )
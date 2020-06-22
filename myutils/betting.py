import re
from queue import Queue
import betfairlightweight
from betfairlightweight.resources.bettingresources import PriceSize, RunnerBookEX
import os
import numpy
import pandas
import logging
from typing import List, Dict


active_logger = logging.getLogger(__name__)

# Change this certs path to wherever you're storing your certificates
certs_path = os.environ['USERPROFILE'] + r'\OneDrive\Betfair\bf certs'

# Change these login details to your own
my_username = "joelyboyrasta@live.co.uk"
my_password = "L0rdTr@d3r"
my_app_key = "TRmlfYWsYKq8IduH"


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
def get_historical(api_client, directory) -> Queue:
    output_queue = Queue()

    listener = betfairlightweight.StreamListener(output_queue=output_queue)
    stream = api_client.streaming.create_historical_stream(
        directory=directory,
        listener=listener
    )
    stream.start()

    return output_queue


# get list of tick increments in encoded integer format
# retrieves list of {'Start', 'Stop', 'Step'} objects from JSON file
def get_tick_increments() -> pandas.DataFrame:
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(cur_dir, "ticks.json")

    with open(file_path) as json_file:
        return pandas.read_json(file_path)


# generate numpy list of ticks from list of {'Start', 'Stop', 'Step'} objects
# output list is complete: [1.00, 1.01, ..., 1000]
def generate_ticks(tick_increments: pandas.DataFrame) -> numpy.ndarray:
    return numpy.concatenate([
        numpy.arange(row.Start, row.Stop, row.Step)
        for index, row in tick_increments.iterrows()
    ])


# encode a floating point number to integer format with x1000 scale
def float_encode(v):
    return round(v*1000)


# decode an integer encoded x1000 scale number to floating point actual value
def int_decode(v):
    return v/1000


class HistoricalProcessor:

    def __init__(self):

        self.i = 0
        self.runners_list = {}
        self.book_attrs = ['available_to_back', 'available_to_lay', 'traded_volume']
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
    def get_odds_array(self, price_list: List[PriceSize], ticks: numpy.ndarray, nearest_tick=False) -> numpy.ndarray:

        # create list of 0s same length as ticks list
        a = numpy.zeros((ticks.shape[0], ))

        for p in price_list:

            # convert "price" (odds value) to encoded integer value
            t = float_encode(p.price)

            # check that price appears in ticks array and get indexes where it does
            indexes = numpy.where(ticks == t)[0]

            if indexes.shape[0]:

                # if index found matching a tick then set the £ value to that index
                a[indexes[0]] = p.size

            else:

                # if index not found print warning
                book = self.book_attrs[self.book_index]
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
    def process_runners(self, historical_list: List, ticks: numpy.ndarray) -> Dict[int, Dict]:

        self.data_count = len(historical_list)
        self.tick_count = len(ticks)

        # loop records
        for self.i, record in enumerate(historical_list):

            # json always has data contained within first element
            record = record[0]

            if self.i == 0:

                # first record - loop runners in market (definition) and create blank arrays to store data
                self.runners_list = {
                    r.selection_id: {
                        'ladder': numpy.zeros([self.data_count, self.tick_count, len(self.book_attrs)]),
                        'last_price_traded': numpy.ndarray((self.data_count, ), dtype=object), # allow for blanks
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
                price_lists = [getattr(book.ex, b) for b in self.book_attrs]
                for self.book_index, self.price_list in enumerate(price_lists):

                    # get array of (tick count) length with price sizes
                    tick_prices = self.get_odds_array(self.price_list, ticks)

                    # assign to: current record (dim 0), current book (dim 2)
                    runner['ladder'][self.i, :, self.book_index] = tick_prices

        return self.runners_list


# GLOBALS
# numpy array of ticks in integer encoded form
TICKS = generate_ticks(get_tick_increments())
# list of Betfair ticks in actual floating values
TICKS_DECODED = int_decode(TICKS).tolist()
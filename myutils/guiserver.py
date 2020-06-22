from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket

from betfairlightweight.resources.bettingresources import MarketBook
import logging
from typing import List, Dict
import threading
from queue import Queue
import numpy
from datetime import datetime, timedelta
import json

from myutils import betting
from myutils import timing


# threading event class that prints when trying to set event and already set, or clear event when already cleared
class VerbalEvent(threading.Event):
    def __init__(self, verbal_name):
        self.verbal_name = verbal_name
        super().__init__()

    def set(self):
        if self.is_set():
            _logger.warning(f'Event "{self.verbal_name}" already set')
        super().set()

    def clear(self):
        if not self.is_set():
            _logger.warning(f'Event "{self.verbal_name}" already cleared')
        super().clear()


# list of SimpleChat client objects (thread safe...?)
_clients = []

# event, which, when set indicates the threads to stop - start in stop position
_stop_event = VerbalEvent('stop server')
_stop_event.set()

# get default logger
_logger = logging.getLogger(__name__)
_in_q = Queue()
_new_client = threading.Event()


# client handling class
class SimpleChat(WebSocket):

    # at present incoming message are not processed, just printed
    def handleMessage(self):
        _logger.debug(f'Message received: {self.data}')
        _in_q.put(self.data)

    def handleConnected(self):
        _logger.info(f'{self.address} connected')
        _clients.append(self)
        _new_client.set()

    def handleClose(self):
        _clients.remove(self)
        _logger.info(f'{self.address} closed')


# run socket server and send messages from queue
def server_operator(server: SimpleWebSocketServer,
                    message_queue: Queue,
                    operating_function=None):

    _logger.info('Starting server operator...')

    # exit once event is set
    while not _stop_event.is_set():

        # run server
        server.serveonce()

        # if operating function passed then call
        if operating_function:
            operating_function()

        # check if messages waiting to be sent
        # (don't check for clients so don't get a massive backlog in-case of client disconnect)
        if not message_queue.empty():

            # get message from queue
            message = message_queue.get()

            # debug log message
            _logger.debug(f'Sending message to {len(_clients)}: {message}')

            # send message to clients
            for client in _clients:
                client.sendMessage(message)

    # exit event set - close server
    _logger.info('Closing server operator...')
    server.close()


# convenience function for starting a thread that operates the server until exit event detected
def server_start(host, port,
                 message_queue: Queue,
                 logger: logging.Logger,
                 operating_function=None):

    # set global logger instance to logger passed as argument
    global _logger
    _logger = logger

    # reset stop event to tell server operator to run
    _stop_event.clear()

    # create SimpleWebSocketServer instance using passed port and host, and custom handler implementation
    server = SimpleWebSocketServer(host, port, SimpleChat)

    # create thread to send outbound messages from queue
    x_server = threading.Thread(target=server_operator, args=(server, message_queue, operating_function))
    x_server.start()


def server_stop():
    _stop_event.set()


class RaceSimulator:

    def __init__(self):

        # local copies of historical record set and runner data
        self.historicalList = numpy.array([], dtype=MarketBook)
        self.processedRunners = None

        # present day timestamp - used to work out time delta in how far along we are in race
        self.presentTimestamp = datetime.now()

        # current time within race
        self.currentTimestamp = None

        # race start timestamp
        self.startTimestamp = None

        # race end timestamp
        self.endTimestamp = None

        # index value in historical list
        self.index = 0

        # array of record timestamps
        self.recordTimestamps = numpy.array([], dtype=datetime)

        # how many seconds on x axis of runner chart
        self.chartSeconds = 60

    # reset present day timer - in other words resets current time delta to 0
    # if presentTimestamp was 18:30 and current time 18:31, then update_race_time() would increment race time by 1 min
    # if reset_simulation_timer() was called prior, presentTimestamp would be reset to 18:31 and update_race_time()
    # would not do anything
    def reset_simulation_timer(self):
        self.presentTimestamp = datetime.now()

    def update_race_time(self):
        delta = datetime.now() - self.presentTimestamp
        _logger.debug(f'Race time delta: {delta}')
        self.currentTimestamp += delta
        self.reset_simulation_timer()

    # assign loaded historical list and runner data to class instance
    def load_race(self, historical_list: List, processed_runners: Dict[int, Dict]):

        # json elements always have a list of single entry, i.e. [data...]
        self.historicalList = numpy.array([record[0] for record in historical_list])
        self.processedRunners = processed_runners

        assert (len(historical_list) and 'expecting non-empty historical list')

        # assign first timestamp to current and race start timestamps
        self.currentTimestamp = self.historicalList[0].publish_time
        self.startTimestamp = self.currentTimestamp

        # assign last timestamp
        self.endTimestamp = self.historicalList[-1].publish_time

        # get timestamps from records
        self.recordTimestamps =  numpy.array([record.publish_time for record in self.historicalList])

    # get index of historical list incrementing on current index position to race timestamp passed
    def _get_next_index(self, index, race_timestamp):

        while 1:

            # check that "next" index is within range
            within_range = (index + 1) < len(self.historicalList)

            if not within_range:

                # if are at 2nd last entry, then return last entry
                return len(self.historicalList) - 1

            elif self.historicalList[index + 1].publish_time > race_timestamp:

                # if "next" index timestamp is beyond race time then "current" index is the appropriate active index
                return index

            else:

                # "next" index is not beyond race time, can increment index
                index += 1

    # wrapper function for updating index and assigning to internal value
    def update_index(self):
        self.index = self._get_next_index(self.index, self.currentTimestamp)

    # get historical index based on how much time (percentage) elapsed from start of recordings
    # returns [race timestamp, index]
    def _get_proportional_index(self, time_percentage: int) -> [datetime, int]:

        if time_percentage < 0 or time_percentage > 100:
            _logger.warning(f'Error, time percentage passed "{time_percentage}" is out of bounds')
            return

        if time_percentage == 0:

            # check dont divide by 0!!
            race_timestamp = self.startTimestamp

        else:

            # get race timestamp based on percentage complete
            race_timestamp = self.startTimestamp + ((self.endTimestamp - self.startTimestamp) * time_percentage / 100)

        # calculate index based on timestamp (start from index 0 as dont know where it will be)
        return [race_timestamp, self._get_next_index(0, race_timestamp)]

    # wrapper function to set index based on proportional time elapsed from start
    def update_proportional_index(self, time_percentage):

        # update race time and historical index based on proportional time elapsed
        [self.currentTimestamp, self.index] = self._get_proportional_index(time_percentage)

        # reset current timestamp so that time delta from last update to present is not added to race time
        self.reset_simulation_timer()

    def get_current_index(self):
        return self.index

    def at_end(self) -> bool:
        return self.index >= len(self.historicalList) - 1

    # get slice of indexes from current datetime passed back (n_seconds)
    def _record_span(self, start_timestamp: datetime) -> slice:

        # initialise slice starting and ending indexes to current
        index_end = self.index
        index_start = self.index

        # decrement starting index - each loop check current index if it is within range
        # NOTE this will include 1 extra
        while index_start > 0 and self.recordTimestamps[index_start] >= start_timestamp:
            index_start -= 1

        return slice(index_start, index_end + 1)

    # get 'x'and 'y' dict of datetimes and last traded price history for a runner object
    def _ltp_history(self, runner: dict, index_slice: slice):

        timestamps = self.currentTimestamp - self.recordTimestamps[index_slice]

        if len(timestamps):
            timestamps[0] = timedelta(0)
            timestamps[-1] = timedelta(seconds=self.chartSeconds)

        return [
            {
                'x': td.total_seconds(),
                'y': ltp
            }
            for [td, ltp] in zip(timestamps, runner['last_price_traded'][index_slice])
        ]

    def get_message(self):
        d0 = self.historicalList[self.index]
        ltp_start_timestamp = self.currentTimestamp - timedelta(seconds=self.chartSeconds)
        ltp_chart_indexes = self._record_span(ltp_start_timestamp)

        data = {
            'type': 'race_update',
            'info': {
                'Race Time': self.currentTimestamp.isoformat(sep=' ', timespec='milliseconds'),
                'Record Time': d0.publish_time.isoformat(sep=' ', timespec='milliseconds'),
                'Market Time': d0.market_definition.market_time.isoformat(sep=' ', timespec='minutes'),
                'Event Name': d0.market_definition.event_name,
                'Name': d0.market_definition.name,
                'Betting Type': d0.market_definition.betting_type,
            },
            'ticks': betting.TICKS_DECODED,
            'runners': {
                id: {
                    'name': runner['market_def'][self.index].name,
                    'status': runner['market_def'][self.index].status,
                    'ladder': runner['ladder'][self.index, :, :].tolist(),
                    'ltp_history': self._ltp_history(runner, ltp_chart_indexes),
                } for id, runner in self.processedRunners.items()
            }
        }

        return json.dumps(data)

    def get_init(self):
        return {
            'type': 'load_race',
            'ticks': betting.TICKS_DECODED,
            'runners': {
                id: {
                    'name': runner['market_def'][0].name,
                    'status': [r.status for r in runner['market_def']],
                    'ladder': runner['ladder'].tolist(),
                    'ltp': runner['last_price_traded'],
                } for id, runner in self.processedRunners.items()
            }
        }

def set_logger(logger):
    # assign global logger passed as arg so it can be accessed by thread
    global _logger
    _logger = logger


class ServerHandler:

    def __init__(self):

        # set inbound message queue to global instance
        self.inboundQ = _in_q

        # create outbound message queue
        self.outboundQ = Queue()

        # create repeating timer instance that produces bool True every 200ms
        self.updateTimer = timing.RepeatingTimer(200)

        # race is "running" indicator
        self.running = VerbalEvent('race running')

        # race simulator instance
        self.raceSimulator = RaceSimulator()

    # wrapper function for RaceSimulator load race
    def load_race(self, historical_list: List, runner_ladders: Dict[int, Dict]):
        self.raceSimulator.load_race(historical_list, runner_ladders)



    # create socket server thread - start listening
    def start_server(self, host, port):
        server_start(host, port, self.outboundQ, _logger)

    # close socket server thread
    def stop_server(self):
        server_stop()

    # set race to start "running"
    def start_running(self):

        _logger.info('Starting race')

        # reset update timer
        self.updateTimer.reset()

        # reset race simulator timer
        self.raceSimulator.reset_simulation_timer()

        # set "race running" indicator event
        self.running.set()

    # set race to stop "running"
    def stop_running(self):

        _logger.info('Stopping race')

        # clear "race running" indicator event
        self.running.clear()

    def handle_input_messages(self):

        # check if input queue has messages
        while not self.inboundQ.empty():

            # get input message
            message_str = self.inboundQ.get()

            # parse to object form
            message = json.loads(message_str)

            # process message
            if 'play' in message['action']:

                # play button pressed
                self.start_running()

            elif 'stop' in message['action']:

                # stop button pressed
                self.stop_running()

            elif 'position' in message['action']:

                # position slider moved
                try:

                    # get position value
                    pos = message['action']['position']
                    _logger.debug(f'Position message received {pos}')

                    # convert to integer
                    pos = int(pos)

                    # update race time and record index values
                    self.raceSimulator.update_proportional_index(pos)

                    # race might not running, so need to send message manually
                    self.send_update()

                except Exception as e:
                    _logger.warning(f'Failed getting race position: {e}', exc_info=True)

    # generate message for current index in historical list and put in outbound queue
    def send_update(self):
        msg = self.raceSimulator.get_message()
        self.outboundQ.put(msg)

    def serve(self):

        # process input message
        self.handle_input_messages()

        # check race is "running"
        if not self.running.is_set():
            return

        # check for end of historical list
        if self.raceSimulator.at_end():
            return

        # check if update period has elapsed and need to send update
        if not self.updateTimer.get():
            return

        # update race time
        self.raceSimulator.update_race_time()

        # update race index
        self.raceSimulator.update_index()

        # send update
        _logger.debug(f'Sending historical index {self.raceSimulator.index} to client...')
        self.send_update()




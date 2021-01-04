import logging
from queue import Queue
from myutils import mylogging


log_q = Queue()

my_handler = mylogging.QueueHandler(log_q)
my_formatter = logging.Formatter(
    fmt='{asctime}: {levelname}: {message}',
    datefmt='%d-%b-%y %H:%M:%S',
    style='{'
)
my_handler.setFormatter(my_formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(
    fmt='{asctime}: {levelname}:{name}: {message}',
    datefmt='%d-%b-%y %H:%M:%S',
    style='{'
))

cb_logger = logging.getLogger('callbacks')
cb_logger.addHandler(my_handler)
cb_logger.addHandler(stream_handler)
cb_logger.setLevel(logging.INFO)



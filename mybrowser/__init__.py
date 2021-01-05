import logging
from queue import Queue
from myutils import mylogging

log_q = Queue()

my_handler = mylogging.QueueHandler(log_q)
my_formatter = logging.Formatter(
    fmt='{asctime}.{msecs:03.0f}: {levelname}:{name}: {message}',
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)
my_handler.setFormatter(my_formatter)

cb_logger = logging.getLogger(__name__)
cb_logger.addHandler(my_handler)
cb_logger.setLevel(logging.INFO)



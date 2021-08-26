import logging
from queue import Queue
from logging import Handler, getLogger, root, StreamHandler


class QueueHandler(Handler):
    def __init__(self, q: Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handler_queue = q

    def emit(self, record):
        try:
            self.handler_queue.put({
                'record': record,
                'txt': self.format(record)
            })
        except Exception:
            self.handleError(record)


def create_dual_logger(name, file_name,
                       file_log_level=logging.DEBUG,
                       stream_log_level=logging.INFO,
                       file_reset=False):
    """
    create a dual logger with a stream and file handlers
    - name: name of logger
    - file_name: file path to use for file handler
    - file_log_level: level of file handler
    - stream_log_level: level of stream handler
    - file_reset: set to True to clear file when file handler created
    """

    # create logger according to active name
    my_logger = logging.getLogger(name)

    # set level to DEBUG so get all messages
    my_logger.setLevel(logging.DEBUG)

    # delete any existing handlers (in case of this code being run twice)
    for h in my_logger.handlers:
        h.close()
    my_logger.handlers.clear()

    # create formatter
    log_formatter = logging.Formatter(
        fmt='{asctime} - {name} - {levelname:8} - {message}',
        datefmt='%d-%b-%y %H:%M:%S',
        style='{'
    )

    # streaming - create handler
    stream_handler = logging.StreamHandler()

    # streaming - assign formatter
    stream_handler.setFormatter(log_formatter)

    # streaming - only want info messages
    stream_handler.setLevel(stream_log_level)

    # file - create handler
    file_handler = logging.FileHandler(file_name, mode='w' if file_reset else 'a')

    # file - assign formatter
    file_handler.setFormatter(log_formatter)

    # file - use debug level for file so get everything
    file_handler.setLevel(file_log_level)

    # set handlers to logger
    my_logger.addHandler(stream_handler)
    my_logger.addHandler(file_handler)

    # print initiation message
    my_logger.info(f'Logger {name} starting...')

    return my_logger


def get_all_loggers():
    """get a dictionary of all loggers"""
    return logging.root.manager.loggerDict

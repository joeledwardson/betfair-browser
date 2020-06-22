import logging


def create_dual_logger(name, file_name,
                       file_log_level=logging.DEBUG,
                       stream_log_level=logging.INFO,
                       file_reset=False):

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
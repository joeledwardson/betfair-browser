
class LadderHistory:

    #
    #   data_count: number of entries
    #   tick_count: number of ticks
    #   logger: logger to use for debugging
    #   start_index: starting index of records, defaults to 0
    def __init__(self, data_count, tick_count, logger: logging.Logger, start_index=0):

        # create new array with dim 0 size as number of records, dim 1 as number of ticks, dim 2 as 3 for atb, atl & tv
        self.data = numpy.ndarray([data_count, tick_count, 3])

        # initialise record indexer
        self.index = start_index

        self.logger = logger
        self.data_len = data_count

    # ignore record by skipping
    def ignore_record(self):
        self.index += 1

    # process runner record
    def process_book_ex(self, book: RunnerBookEX, ticks):

        # check index has not exceed array length
        if self.index >= self.data_len:
            logging.error(f'Tried to process book at index {self.index} when len specified is {self.data_len}')
            return

        # create array pointing to atb, atl & tv books to process
        books = [book.available_to_back, book.available_to_lay, book.traded_volume]
        for i, price_list in enumerate(books):

            # get array of (tick count) length with price sizes
            tick_prices = get_odds_array(price_list, ticks)
            # assign to: current record (dim 0), current book (dim 2)
            self.data[self.index, :, i] = tick_prices

        # increment record indexer
        self.index += 1

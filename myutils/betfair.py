from betfairlightweight import StreamListener
from betfairlightweight.exceptions import ListenerError
from betfairlightweight.streaming import BaseListener


class BufferStream:
    def __init__(
        self, data: str, listener: BaseListener, operation: str, unique_id: int
    ):
        self.data = data
        self.listener = listener
        self.operation = operation
        self.unique_id = unique_id
        self._running = False

    @staticmethod
    def generator(
            data: str = None,
            listener: BaseListener = None,
            operation: str = "marketSubscription",
            unique_id: int = 0,
    ) -> 'BufferStream':
        listener = listener if listener else StreamListener()
        return BufferStream(data, listener, operation, unique_id)

    def start(self) -> None:
        self._running = True
        self._read_loop()

    def stop(self) -> None:
        self._running = False

    def _read_loop(self) -> None:
        self.listener.register_stream(self.unique_id, self.operation)
        for update in self.data.splitlines():
            if self.listener.on_data(update) is False:
                # if on_data returns an error stop the stream and raise error
                self.stop()
                raise ListenerError("HISTORICAL", update)
            if not self._running:
                break
        self.stop()
from typing import Optional

from flumine import clients

# TODO - client/strategies can be merged into single file
class BackTestClientNoMin(clients.BacktestClient):
    """
    flumine back test client with no minimum bet size
    """
    @property
    def min_bet_size(self) -> Optional[float]:
        return 0
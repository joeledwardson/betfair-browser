from mytrading.tradetracker.tradetracker import TradeTracker


class WindowTradeTracker(TradeTracker):
    # direction of LTP window breach is up (false for down)
    direction_up: bool = False



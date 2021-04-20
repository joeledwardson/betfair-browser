from mytrading.strategy.tradetracker.tradetracker import TradeTracker


class TrendTradeTracker(TradeTracker):
    # direction of LTP window breach is up (false for down)
    direction_up: bool = False




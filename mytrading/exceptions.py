class MyTradingException(Exception):
    """base exception"""
    pass


class FigureException(MyTradingException):
    pass


class FigureProcessException(FigureException):
    pass


class FigureDataProcessorException(FigureProcessException):
    pass


class FigurePostProcessException(FigureProcessException):
    pass


class FigEmptyException(FigureProcessException):
    pass


class TradeTrackerException(MyTradingException):
    pass


class TradeStateException(MyTradingException):
    pass


class MyStrategyException(MyTradingException):
    pass


class MessagerException(MyTradingException):
    pass


class FeatureException(MyTradingException):
    pass


class BfProcessException(MyTradingException):
    pass
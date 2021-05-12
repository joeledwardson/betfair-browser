class MyUtilsException(Exception):
    pass


class RegistrarException(MyUtilsException):
    pass


class StateMachineException(MyUtilsException):
    pass


class TimingException(MyUtilsException):
    """A custom exception used to report errors in use of Timer class"""
    pass


class DictException(MyUtilsException):
    pass
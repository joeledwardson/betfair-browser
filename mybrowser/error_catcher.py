from .exceptions import MyBrowserException
from .session import Notification, post_notification
from typing import List, Callable, Any
from mytrading.exceptions import MyTradingException
from myutils.exceptions import MyUtilsException
from sqlalchemy.exc import SQLAlchemyError
import traceback
import functools

exceptions = (
    MyBrowserException,
    MyUtilsException,
    MyTradingException,
    ValueError,
    KeyError,
    TypeError,
    SQLAlchemyError
)


def handle_errors(notifs: List[Notification], action: str):
    def outer(process: Callable):
        def inner(*args, **kwargs):
            try:
                return process(*args, **kwargs)
            except exceptions as e:
                msg = f'exception: "{e}"\ntraceback:\n{traceback.format_exc()}'
                post_notification(notifs, 'danger', action, msg)
        return inner
    return outer
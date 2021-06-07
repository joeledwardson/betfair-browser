class MyBrowserException(Exception):
    pass


class LayoutException(MyBrowserException):
    pass


class SessionException(MyBrowserException):
    pass


class UrlException(MyBrowserException):
    pass
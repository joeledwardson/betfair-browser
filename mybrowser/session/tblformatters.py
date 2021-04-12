from myutils.myregistrar import MyRegistrar
from datetime import date, datetime


def get_formatters(config):
    formatters = MyRegistrar()

    @formatters.register_element
    def format_datetime(dt: datetime):
        return dt.strftime(config['FORMATTERS_CONFIG']['dt_format'])

    return formatters
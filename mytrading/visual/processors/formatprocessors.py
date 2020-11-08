from typing import Dict, List

import pandas as pd
format_processors = {}


def register_format_processor(func):
    """
    register a format processor, add to dictionary of processors
    signature:

    def func(value, feature_name, **kwargs)
    """
    if func.__name__ in format_processors:
        raise Exception(f'registering plotly format processor "{func.__name__}", but already exists!')
    else:
        format_processors[func.__name__] = func
        return func


@register_format_processor
def formatter_percent(value, name, n_decimals=0) -> str:
    """
    format value with name to percentage with 'n_decimals' dp
    """
    return f'{name}: {value:.{n_decimals}%}'


@register_format_processor
def formatter_decimal(value, name, n_decimals=2, prefix='') -> str:
    """
    format value with name to decimal with 'n_decimals' dp
    """
    return f'{name}: {prefix}{value:.{n_decimals}f}'


@register_format_processor
def formatter_regression(value, rsqaured_dp=0, gradient_dp=2) -> str:
    """
    format regression dictionary with 'gradient' and 'rsquared' attributes
    Parameters
    ----------
    value :
    name :

    Returns
    -------

    """
    if type(value) is dict:
        rsquared = value.get('rsquared', 0)
        gradient = value.get('gradient', 0)
        return f'regression:<br>' \
               f'-> r-squared: {rsquared:.{rsqaured_dp}%}<br>' \
               f'-> gradient: {gradient:.{gradient_dp}%}'
    else:
        return ''


@register_format_processor
def formatter_pricesize(value):
    """
    convert a list of price sizes to a html friendly display string
    """
    if type(value) is list:
        return '<br>'.join([f'price: {ps["price"]}, size: £{ps["size"]:.2f}' for ps in value])
    else:
        return ''


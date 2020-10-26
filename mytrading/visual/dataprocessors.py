from typing import Dict, List
import pandas as pd
from .formatprocessors import format_processors
from functools import partial

plotly_processors = {}


def register_data_processor(func):
    """
    register a plotly processor, add to dictionary of processors
    signature:

    def func(data, features, **kwargs)
    """
    if func.__name__ in plotly_processors:
        raise Exception(f'registering plotly data processor {func.__name__}, but already exists!')
    else:
        plotly_processors[func.__name__] = func
        return func


def process_plotly_data(data, features, processors_config):
    """
    use plotly data processors to process data
    """
    for cfg in processors_config:
        func = plotly_processors[cfg['name']]
        kwargs = cfg.get('kwargs', {})
        data = func(data, features, **kwargs)
    return data


def remove_duplicates(data: pd.Series) -> pd.Series:
    """
    remove duplicates from series with datetime index keeping last value
    """
    return data[~data.index.duplicated(keep='last')]


@register_data_processor
def plotly_df_to_data(data: pd.DataFrame, features) -> Dict:
    """
    convert dataframe to dictionary (assuming columns are appropriate for plotly chart arg) and use index for 'x' vals
    """
    values = data.to_dict(orient='list')
    values.update({'x': data.index})
    return values


@register_data_processor
def plotly_series_to_data(data: pd.Series, features) -> Dict:
    """
    convert series to dictionary with 'x' and 'y'
    """
    return {
        'x': data.index,
        'y': data.to_list()
    }


@register_data_processor
def plotly_regression(data: Dict, features) -> Dict:
    """
    convert returned values dict from 'RunnerFeatureRegression' feature into plotly compatible dict with 'x',
    'y' and 'text'
    """
    txt_rsqaured = f'rsquared: {data["rsquared"]:.2f}'
    return {
        'x': data['dts'],
        'y': data['predicted'],
        'text': [txt_rsqaured for x in data['dts']]
    }


@register_data_processor
def values_resampler(data: pd.DataFrame, features, n_seconds, sampling_function='last') -> pd.DataFrame:
    """
    resample 'df' DataFrame for 'n_seconds', using last value each second and forward filling
    can override default sampling function 'last' with `sampling_function` arg
    """
    rule = f'{n_seconds}S'
    return data.resample(rule).apply(sampling_function).fillna(method='ffill') if data.shape[0] else data


@register_data_processor
def plotly_data_to_series(data: dict, features) -> pd.Series:
    """
    convert 'data' x-y plotly values (dict with 'x' and 'y' indexed list values) to pandas series where index is 'x'
    """
    return pd.Series(data['y'], index=data['x'])


@register_data_processor
def plotly_pricesize_display(data: Dict, features):
    """
    convert a list of price sizes to a html friendly display string
    """
    return {
        'x': data['x'],
        'y': [
            '<br>'.join([f'price: {ps["price"]}, size: £{ps["size"]:.2f}' for ps in ps_list])
            for ps_list in data['y']
        ]
    }


@register_data_processor
def plotly_set_attrs(
        data: Dict,
        features,
        feature_name,
        feature_value_processors,
        attr_configs: List[Dict],
) -> pd.DataFrame:
    """
    For a given dictionary 'vals' of plotly data containing 'x' and 'y' lists of values, set additional dictionary
    attributes to be accepted by a plotly chart function

    - 'name': feature name of which to get data from
    - 'data_processors': data processors configuration to apply to feature


    'feature_configs' dictionary specifies what features to use as additional attributes and how to process them
    - list of feature configuration dictionaries:
    -   'name': feature name to get values from (only first index from values list is used!)
    -   'processors': list of processor(data: dict) functions to run on data retrieved from feature
    -   'attr formatters': dictionary of:
    -       key: attribute name to set in plotly dictionary
    -       value: formatter(value) to format data into visualisation form
    """

    # have to remove duplicate datetime indexes from each series or pandas winges when trying to make a dataframe
    sr_data = plotly_data_to_series(data, features)
    sr_data = remove_duplicates(sr_data)

    df_data = {
        'y': sr_data,
    }

    assert(type(attr_configs) is list)

    # get data from feature to be used as color in plot (assume single plotting element)
    attr_data = features[feature_name].get_plotly_data()[0]
    attr_data = process_plotly_data(attr_data, features, feature_value_processors)

    # check has x and y values
    if 'y' in data and len(data['y']) and 'x' in data and len(data['x']):

        # create series and remove duplicates from color data
        sr_attr = pd.Series(attr_data['y'], index=attr_data['x'])
        sr_attr = remove_duplicates(sr_attr)

        for cfg in attr_configs:

            formatter_name = cfg.get('formatter_name')
            if formatter_name:
                formatter = format_processors[formatter_name]
                formatter_kwargs = cfg.get('formatter_kwargs', {})
                sr_attr_final = sr_attr.apply(partial(formatter, **formatter_kwargs))
            else:
                sr_attr_final = sr_attr

            attr_name = cfg['attr_name']
            df_data[attr_name] = sr_attr_final

    df = pd.DataFrame(df_data)
    df = df.fillna(method='ffill')
    return df



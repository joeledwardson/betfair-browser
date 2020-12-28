from betfairlightweight.resources.bettingresources import MarketBook
from flumine.markets.market import Market
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import os
from .process.names import names_to_id, name_processor, get_names
from .utils.storage import get_hist_cat, EXT_CATALOGUE


oc_logger = logging.getLogger('')
OC_EXCHANGES = ['BF', 'MK', 'MA', 'BD', 'BQ']
EXT_ODDSCHECKER = '.oddschecker'
# SUBDIR_OC = 'oddschecker'


def tr_odds(tr):
    backs = {}
    for td in tr.find_all('td'):
        if 'data-bk' and 'data-odig' in td.attrs:
            odds = td.attrs['data-odig']
            try:
                odds = float(odds)
                if odds:
                    backs[td.attrs['data-bk']] = odds
            except ValueError as e:
                pass
    return backs


def table_odds(tbl_body):
    dat = []
    names = []
    for i, tr in enumerate(tbl_body.find_all('tr')):
        if 'data-bname' in tr.attrs:
            name = tr.attrs['data-bname']
            names.append(name)
            oc_logger.debug(f'new name "{name}" found')
            dat.append(tr_odds(tr))
        else:
            oc_logger.debug(f'no "data-bname" element found in row {i}')
    return pd.DataFrame(dat, index=names)


class OCException(Exception):
    pass


raw_venues = {
    'Nottingham': 'Nottingham BAGS',
    'Kinsley': 'Kinsley BAGS',
    # 'Sunderland': 'Sunderland BAGS',
    'Sheffield': 'Sheffield BAGS',
    'Swindon': 'Swindon BAGS',
    'Newcastle': 'Newcastle BAGS',
    'Perry Barr': 'Perry Barr BAGS'
}


# conversion from betfair venues to odschecker venues
venue_map = {name_processor(k): v for (k,v) in raw_venues.items()}


# construct oddschecker url (datetime must be in UK localised with daylight savings form)
def url(sport, dt: datetime, venue, odds_type='winner', _venue_map={}):

    # get date and time strings (as oddschecker constructs them)
    _date = dt.strftime('%Y-%m-%d')
    _time = dt.strftime('%H:%M')

    if sport == 'greyhounds':
        _venue_map = venue_map

    # convert to oddschecker venue name
    venue = _venue_map.get(name_processor(venue)) or venue

    # replace spaces with dashes for url
    venue = venue.replace(' ', '-')

    return f'https://oddschecker.com/{sport}/{_date}-{venue}/{_time}/{odds_type}'


def oc(url):
    oc_logger.info(f'requesting url "{url}"')

    resp = requests.get(url)
    if not resp.ok:
        raise OCException(f'error requesting url, code {resp.status_code}')
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", {"class": "eventTable"})
    if not table:
        raise OCException(f'could not find table element')

    if not hasattr(table, 'tbody'):
        raise OCException(f'table does not have "tbody" element')

    trs = table.tbody.find_all('tr')
    oc_logger.debug(f'found {len(trs)} "tr" elements in table')
    return table_odds(table.tbody)


def oc_to_file(file_path, sport, dt: datetime, venue, odds_type='winner'):

    # get oddschecker url
    oc_url = url(sport, dt, venue, odds_type)

    # scrape data
    try:
        df = oc(oc_url)
    except OCException as e:
        oc_logger.warning('odds checker exception', exc_info=True)
        return

    # create dirs
    d = os.path.dirname(file_path)
    os.makedirs(d, exist_ok=True)

    # write pickled to file
    oc_logger.info(f'writing pickled oddschecker to "{file_path}"')
    df.to_pickle(file_path)


def sort_oc(df: pd.DataFrame) -> pd.DataFrame:
    """sort oddschecker dataframe by average value"""

    # get means across columns
    avgs = df.mean(axis=1)
    return avgs.sort_values()


def get_hist_oc_df(oc_path) -> pd.DataFrame:
    """get historical oddschecker file"""
    try:
        return pd.read_pickle(oc_path)
    except Exception as e:
        oc_logger.warning(f'error getting oc file: "{e}"', exc_info=True)
        return None


def process_oc_df(df: pd.DataFrame, name_id_map):
    """
    strip exchanges from oddschecker odds dataframe columns and dataframe index (names) with selection IDs on fail,
    will log an error and return None
    """

    df = df[[col for col in df.columns if col not in OC_EXCHANGES]]
    oc_ids = names_to_id(df.index, name_id_map)
    if not oc_ids:
        return None

    df.index = oc_ids
    return df


def oc_hist_mktbk_processor(
        market_id: str,
        market_path,
        name_attr='name'):
    """
    function searches for betfair catalogue file and oddschecker dataframe file
    - if processed successfully, d['ok'] is True
    """

    d = {
        'ok': False,
    }

    # oc_logger.info('processing new market "{}" {} {}'.format(
    #     market_book.market_id,
    #     market_book.market_definition.market_time,
    #     market_book.market_definition.event_name
    # ))

    # get oddschecker dataframe from file
    oc_df = get_hist_oc_df(os.path.join(
        market_path,
        market_id + EXT_ODDSCHECKER
    ))
    if oc_df is None:
        return d

    # get betfair category from file
    cat = get_hist_cat(os.path.join(
        market_path,
        market_id + EXT_CATALOGUE
    ))
    if cat is None:
        return d

    # process oddschecker dataframe to set with selection IDs
    try:
        name_id_map = get_names(cat, name_attr=name_attr, name_key=True)
    except Exception as e:
        oc_logger.warning(f'couldnt get names: {e}')
        return d
    oc_df = process_oc_df(oc_df, name_id_map)
    if oc_df is None:
        return d

    # assign results to dict and write as market attribute
    oc_sorted = sort_oc(oc_df)
    d['oc_df'] = oc_df
    d['oc_sorted'] = oc_sorted
    d['id_fav'] = oc_sorted.index[0]
    d['id_outsider'] = oc_sorted.index[-1]
    d['cat'] = cat
    d['ok'] = True
    return d
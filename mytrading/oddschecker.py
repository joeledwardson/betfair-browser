import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import os
from mytrading.betting import name_processor

oc_logger = logging.getLogger('')

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
            logging.debug(f'new name "{name}" found')
            dat.append(tr_odds(tr))
        else:
            logging.debug(f'no "data-bname" element found in row {i}')
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
    logging.info(f'requesting url "{url}"')

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
    logging.debug(f'found {len(trs)} "tr" elements in table')
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


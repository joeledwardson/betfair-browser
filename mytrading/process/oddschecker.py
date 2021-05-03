import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re
import yaml
from typing import Dict, List
from ..exceptions import OCException


oc_logger = logging.getLogger('')
OC_EXCHANGES = ['BF', 'MK', 'MA', 'BD', 'BQ']


def name_processor(name):
    """remove all characters not in alphabet and convert to lower case"""
    return re.sub('[^a-zA-Z]', '', name).lower()


def _validate_names(names: List):
    l1 = len(names)
    l2 = len(set(name_processor(nm) for nm in names))
    if l1 != l2:
        raise OCException(f'processed names have duplicated, original:\n{yaml.dump(names)}')


def convert_names(odds: Dict, names: Dict) -> Dict:
    _validate_names(list(names.values()))
    _validate_names(list(odds.keys()))
    # process names and invert from (ID: name) to (processed name: ID)
    prc_names = {
        name_processor(v): k
        for k, v in names.items()
    }
    # convert from (OC name: OC odds dict) to (ID: OC odds dict)
    prc_odds = {}
    for nm, v in odds.items():
        prc_nm = name_processor(nm)
        if prc_nm not in prc_names.keys():
            raise OCException(f'processed name "{prc_nm}" not found in name list')
        _id = prc_names[prc_nm]
        prc_odds[_id] = v
    return prc_odds


def tr_odds(tr):
    """get dictionary of (bookmaker: odds) from table row"""
    backs = {}
    for td in tr.find_all('td'):
        if 'data-bk' and 'data-odig' in td.attrs:
            odds = td.attrs['data-odig']
            try:
                odds = float(odds)
                if odds:
                    backs[td.attrs['data-bk']] = odds
            except ValueError:
                pass
    return backs


def table_odds(tbl_body) -> Dict:
    """get dataframe with index as runner name, columns as bookmakers and value as odds from html table body"""
    dat = {}
    for i, tr in enumerate(tbl_body.find_all('tr')):
        if 'data-bname' in tr.attrs:
            name = tr.attrs['data-bname']
            oc_logger.debug(f'new name "{name}" found')
            dat.update({name: tr_odds(tr)})
        else:
            oc_logger.debug(f'no "data-bname" element found in row {i}')
    return dat


# greyhound mappings from betfair venues to oddschecker venues
gh_venues = {
    'nottingham': 'nottingham-bags',
    'kinsley': 'kinsley-bags',
    'sunderland': 'sunderland-bags',
    'sheffield': 'sheffield-bags',
    'swindon': 'swindon-bags',
    'newcastle': 'newcastle-bags',
}


def oc_url(sport, dt: datetime, venue, odds_type='winner'):
    """construct oddschecker url (datetime must be in UK localised with daylight savings form)"""

    # get date and time strings (as oddschecker constructs them)
    _date = dt.strftime('%Y-%m-%d')
    _time = dt.strftime('%H:%M')

    if sport == 'greyhounds':
        _venue_map = gh_venues
    else:
        _venue_map = {}

    # convert to oddschecker venue name
    venue = _venue_map.get(name_processor(venue)) or venue

    return f'https://oddschecker.com/{sport}/{_date}-{venue}/{_time}/{odds_type}'


def oc(url) -> Dict:
    oc_logger.info(f'requesting oddschecker url "{url}"')

    resp = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
    })
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


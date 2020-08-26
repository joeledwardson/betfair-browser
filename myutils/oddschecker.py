import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup

def tr_odds(tr):
    backs = {}
    for td in tr.find_all('td'):
        if 'data-bk' and 'data-odig' in td.attrs:
            odds = td.attrs['data-odig']
            try:
                odds = float(odds)
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
from dataclasses import dataclass
from typing import List

from mytrading.utils import dbfilter as dbf
from myutils.dashutilities import interface as comp


@dataclass
class MarketFilter:
    component_id: str
    component: any
    filter: dbf.DBFilter


def get_market_filters() -> List[MarketFilter]:
    id_sport = 'input-sport-type'
    id_market_type = 'input-market-type'
    id_bet_type = 'input-bet-type'
    id_format = 'input-format'
    id_country_code = 'input-country-code'
    id_venue = 'input-venue'
    id_date = 'input-date'
    id_market = 'input-market-id'

    return [
        MarketFilter(
            id_sport,
            comp.select(id_sport, placeholder='Sport...'),
            dbf.DBFilterJoin(
                db_col='sport_id',
                join_tbl_name='sportids',
                join_id_col='sport_id',
                join_name_col='sport_name'
            )
        ),
        MarketFilter(
            id_market_type,
            comp.select(id_market_type, placeholder='Market type...'),
            dbf.DBFilter(db_col='market_type')
        ),
        MarketFilter(
            id_bet_type,
            comp.select(id_bet_type, placeholder='Betting type...'),
            dbf.DBFilter(db_col='betting_type')
        ),
        MarketFilter(
            id_format,
            comp.select(id_format, placeholder='Format...'),
            dbf.DBFilter(db_col='format')
        ),
        MarketFilter(
            id_country_code,
            comp.select(id_country_code, placeholder='Country...'),
            dbf.DBFilterJoin(
                db_col="country_code",
                join_tbl_name='countrycodes',
                join_id_col='alpha_2_code',
                join_name_col='name'
            )
        ),
        MarketFilter(
            id_venue,
            comp.select(id_venue, placeholder='Venue...'),
            dbf.DBFilter(db_col='venue')
        ),
        MarketFilter(
            id_date,
            comp.select(id_date, placeholder='Market date...'),
            dbf.DBFilterDate(
                db_col='market_time',
                dt_fmt='%d %b %y'
            )
        ),
        MarketFilter(
            id_market,
            comp.input_component(id_market, placeholder='Market ID filter...'),
            dbf.DBFilterText(db_col='market_id')
        )
    ]


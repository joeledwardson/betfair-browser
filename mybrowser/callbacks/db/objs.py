import logging
from ...dbdefs import DateFilter, JoinedFilter, DBFilter, reg, formatters, DBTable
from ...config import config

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


filter_sport = JoinedFilter(
    "sport_id",
    'MARKETFILTERS',
    join_tbl_name='sportids',
    join_id_col='sport_id',
    join_name_col='sport_name'
)
filter_country = JoinedFilter(
    "country_code",
    'MARKETFILTERS',
    join_tbl_name='countrycodes',
    join_id_col='alpha_2_code',
    join_name_col='name'
)
filter_format = DBFilter(
    'format',
    'MARKETFILTERS'
)
filter_type = DBFilter(
    "market_type",
    'MARKETFILTERS'
)
filter_bet = DBFilter(
    "betting_type",
    'MARKETFILTERS'
)
filter_venue = DBFilter(
    "venue",
    'MARKETFILTERS'
)
filter_date = DateFilter(
    "market_time",
    'MARKETFILTERS'
)


filter_strat_select = DBFilter(
    'strategy_id',
    'STRATEGYFILTERS'
)

market_table = DBTable(
    id_col='market_id',
    max_rows=int(config['DB']['max_rows']),
    fmt_config=config['TABLEFORMATTERS'],
    pg_size=int(config['TABLE']['page_size']),
)


market_filters = {
    'input-sport-type': filter_sport,
    'input-mkt-type': filter_type,
    'input-bet-type': filter_bet,
    'input-format': filter_format,
    'input-country-code': filter_country,
    'input-venue': filter_venue,
    'input-date': filter_date,
}

import logging
from .filtertypes import DateFilter, JoinedFilter, DBFilter

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


mkt_sport = JoinedFilter(
    "sport_id",
    'MARKETFILTERS',
    join_tbl_name='sportids',
    join_id_col='sport_id',
    join_name_col='sport_name'
)
mkt_country = JoinedFilter(
    "country_code",
    'MARKETFILTERS',
    join_tbl_name='countrycodes',
    join_id_col='alpha_2_code',
    join_name_col='name'
)
mkt_format = DBFilter(
    'format',
    'MARKETFILTERS'
)
mkt_type = DBFilter(
    "market_type",
    'MARKETFILTERS'
)
mkt_bet = DBFilter(
    "betting_type",
    'MARKETFILTERS'
)
mkt_venue = DBFilter(
    "venue",
    'MARKETFILTERS'
)
mkt_date = DateFilter(
    "market_time",
    'MARKETFILTERS'
)


strat_id = DBFilter(
    'strategy_id',
    'STRATEGYFILTERS'
)

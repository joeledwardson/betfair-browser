import logging
from .dbfilter import DBFilterDate, DBFilterJoin, DBFilter, DBFilterMulti

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class DBFilters:

    def filters_values(self, group):
        return [flt.value for flt in DBFilter.reg[group]]

    def filters_labels(self, group, db, cte):
        return [
            flt.get_labels(flt.get_options(db, cte))
            for flt in DBFilter.reg[group]
        ]

    def update_filters(self, group, clear, *args):
        assert len(args) == len(DBFilter.reg[group])
        for val, flt in zip(args, DBFilter.reg[group]):
            flt.set_value(val, clear)

    def __init__(self, mkt_dt_fmt, strat_sel_fmt):
        self.filters = [
            DBFilterJoin(
                "sport_id",
                'MARKETFILTERS',
                join_tbl_name='sportids',
                join_id_col='sport_id',
                join_name_col='sport_name'
            ),
            DBFilter(
                "market_type",
                'MARKETFILTERS'
            ),
            DBFilter(
                "betting_type",
                'MARKETFILTERS'
            ),
            DBFilter(
                'format',
                'MARKETFILTERS'
            ),
            DBFilterJoin(
                "country_code",
                'MARKETFILTERS',
                join_tbl_name='countrycodes',
                join_id_col='alpha_2_code',
                join_name_col='name'
            ),
            DBFilter(
                "venue",
                'MARKETFILTERS'
            ),
            DBFilterDate(
                "market_time",
                'MARKETFILTERS',
                mkt_dt_fmt
            ),

            DBFilterMulti(
                'strategy_id',
                'STRATEGYFILTERS',
                fmt_spec=strat_sel_fmt,
                order_col='exec_time',
                is_desc=True,
            )
        ]

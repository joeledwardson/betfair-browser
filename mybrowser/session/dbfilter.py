from typing import Dict, List
from sqlalchemy import func, cast, Date, desc
from sqlalchemy.sql.functions import coalesce
from ..config import config
from datetime import date, datetime


class DBFilter:

    reg: Dict[str, List] = {}

    def __init__(self, db_col, group):
        self.db_col = db_col
        self.value = None
        self.group = group
        if group not in DBFilter.reg:
            DBFilter.reg[group] = []
        DBFilter.reg[group].append(self)

    def set_value(self, value, clear):
        if clear:
            self.value = None
        else:
            self.value = value

    def db_filter(self, meta):
        return meta.columns[self.db_col] == self.value

    def get_options(self, db, cte):
        return db.session.query(cte.c[self.db_col]).distinct().all()

    # TODO - remove dash specific 'label' and 'value'
    def get_labels(self, opts):
        return [{
            'label': row[0],
            'value': row[0],
        } for row in opts]


class DateFilter(DBFilter):

    def set_value(self, value, clear):
        if value is not None:
            value = date.fromisoformat(value)
        super().set_value(value, clear)

    def db_filter(self, meta):
        return cast(meta.columns[self.db_col], Date) == self.value

    def get_options(self, db, cte):
        date_col = cast(cte.c[self.db_col], Date)
        return db.session.query(date_col).distinct().order_by(desc(date_col)).all()

    def get_labels(self, opts):
        return [{
            'label': row[0].strftime(config['MARKET_FILTER']['date_format']),
            'value': row[0],
        } for row in opts]


class JoinedFilter(DBFilter):

    def __init__(self, db_col, filter_group, join_tbl_name, join_id_col, join_name_col):
        super().__init__(db_col, filter_group)
        self.join_tbl_name = join_tbl_name
        self.join_id_col = join_id_col
        self.join_name_col = join_name_col
        self.output_col = 'TEMP_OUTPUT_NAME'

    def get_options(self, db, cte):
        join_tbl = db.tables[self.join_tbl_name]
        q = db.session.query(
            cte.c[self.db_col],
            coalesce(
                join_tbl.columns[self.join_name_col],
                cte.c[self.db_col]
            ).label(self.output_col)
        ).join(
            join_tbl,
            cte.c[self.db_col] == join_tbl.columns[self.join_id_col],
            isouter=True
        ).distinct()
        return q.all()

    def get_labels(self, opts):
        return [{
            'label': dict(row)[self.output_col],
            'value': dict(row)[self.db_col]
        } for row in opts]


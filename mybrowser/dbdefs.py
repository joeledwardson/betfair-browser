import dash
from dash.dependencies import Output, Input, State
from sqlalchemy import func, cast, Date, desc
from sqlalchemy.sql.functions import coalesce
from .data import DashData
from .config import config
from myutils.mydash import intermediate
from myutils.mydash.context import triggered_id
from myutils.mydash import context as my_context
from myutils.mydash import dashtable
from myutils.myregistrar import MyRegistrar
from mytrading.utils.bettingdb import BettingDB
import logging
from datetime import date, datetime
from functools import partial

reg = {}
formatters = MyRegistrar()


@formatters.register_element
def format_datetime(dt: datetime):
    return dt.strftime(config['TABLE']['dt_format'])


class DBFilter:
    def __init__(self, db_col, group):
        self.db_col = db_col
        self.value = None
        if group not in reg:
            reg[group] = []
        reg[group].append(self)

    def set_value(self, value, clear):
        if clear:
            self.value = None
        else:
            self.value = value

    def db_filter(self, meta):
        return meta.columns[self.db_col] == self.value

    def get_options(self, db, cte):
        return db.session.query(cte.c[self.db_col]).distinct().all()

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


class DBTable:

    def __init__(self, id_col, max_rows, fmt_config, pg_size):
        self.id_col = id_col
        self.max_rows = max_rows
        self.fmt_config = fmt_config
        self.page_size = pg_size
        self.q_final = None
        self.q_result = None

    def table_output(self, tbl_cols, db):
        self.q_final = db.session.query(*tbl_cols).limit(self.max_rows)
        self.q_result = self.q_final.all()
        tbl_rows = [dict(r) for r in self.q_result]
        for i, row in enumerate(tbl_rows):

            # set 'id' column value to betfair id so that dash will set 'row-id' within 'active_cell' correspondingly
            row['id'] = row[self.id_col]

            # apply custom formatting to table row values
            for k, v in row.items():
                if k in self.fmt_config:
                    nm = self.fmt_config[k]
                    f = formatters[nm]
                    row[k] = f(v)

        # pad table rows to page size if necessary
        # dashtable.pad(tbl_rows, self.page_size)

        return tbl_rows

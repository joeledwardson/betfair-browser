from typing import Dict, List, Any
from sqlalchemy import func, cast, Date, desc, asc, Table
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.sql import cte
from datetime import date, datetime
from mytrading.utils import bettingdb as bdb


class DBFilter:
    """
    database filter for a column of a table
    designed to present a list of options with values that correspond to database value, and labels that can be
    customised for display

    all instances are registered to a dictionary in lists according to 'group' specified on initialisation
    """

    reg: Dict[str, List] = {}

    def __init__(self, db_col: str, group: str):
        """
        set db_col to the name of the database column on which it will apply a filter
        group is the text name of the group to register the instance to
        """
        self.db_col = db_col
        self.value = None
        self.group = group
        if group not in DBFilter.reg:
            DBFilter.reg[group] = []
        DBFilter.reg[group].append(self)

    def set_value(self, value, clear: bool):
        """
        store value selected by user using 'value', or clear stored value by setting 'clear' to True
        """
        if clear:
            self.value = None
        else:
            self.value = value

    def db_filter(self, tbl: Table):
        """
        return a SQLAlchemy filter of the specified column at initialisation of the table passed as 'tbl' filtered to
        the stored value
        """
        return tbl.columns[self.db_col] == self.value

    def get_options(self, db: bdb.BettingDB, db_cte: cte) -> List[List[Any]]:
        """
        get a list of distinct values from database
        """
        return db.session.query(db_cte.c[self.db_col]).distinct().all()

    def get_labels(self, opts: List[List[Any]]) -> List[Dict[str, Any]]:
        """
        get a list of dicts with 'label' and 'value' set (in accordance to plotly dash datatable)
        """
        return [{
            'label': row[0],
            'value': row[0],
        } for row in opts]


class DBFilterDate(DBFilter):
    """
    Date specific type of database filter, can set format of date printed as label
    """

    def __init__(self, db_col, group, dt_fmt):
        super().__init__(db_col, group)
        self.dt_fmt = dt_fmt

    def set_value(self, value, clear):
        """
        pass value as a string which is formatted to datetime object
        """
        if value is not None:
            value = date.fromisoformat(value)
        super().set_value(value, clear)

    def db_filter(self, meta):
        return cast(meta.columns[self.db_col], Date) == self.value

    def get_options(self, db, db_cte):
        """
        get options starting from most recent date first
        """
        date_col = cast(db_cte.c[self.db_col], Date)
        return db.session.query(date_col).distinct().order_by(desc(date_col)).all()

    def get_labels(self, opts):
        """
        format labels with datetime format passed to constructor
        """
        return [{
            'label': row[0].strftime(self.dt_fmt),
            'value': row[0],
        } for row in opts]


class DBFilterJoin(DBFilter):
    """
    Join a table to another database filter, where `db_col` specified should map to another column in the database
    whose table is `join_tbl_name` and whose name is `join_id_col`. `join_name_col` specified the column in the other
    table that is used to present in labels.
    """
    def __init__(self, db_col, group, join_tbl_name, join_id_col, join_name_col):
        super().__init__(db_col, group)
        self.join_tbl_name = join_tbl_name
        self.join_id_col = join_id_col
        self.join_name_col = join_name_col
        self.output_col = 'TEMP_OUTPUT_NAME'

    def get_options(self, db: bdb.BettingDB, db_cte: cte):
        join_tbl = db.tables[self.join_tbl_name]
        q = db.session.query(
            db_cte.c[self.db_col],
            coalesce(
                join_tbl.columns[self.join_name_col],
                db_cte.c[self.db_col]
            ).label(self.output_col)
        ).join(
            join_tbl,
            db_cte.c[self.db_col] == join_tbl.columns[self.join_id_col],
            isouter=True
        ).distinct()
        return q.all()

    def get_labels(self, opts):
        return [{
            'label': dict(row)[self.output_col],
            'value': dict(row)[self.db_col]
        } for row in opts]


class DBFilterMulti(DBFilter):
    """
    Filter to 1 column but use other columns in table to construct label, whereby `fmt_spec` is the string formatting
    specifier used to construct the labels

    e.g. `fmt_spec`='{sport_name}, {sport_time}`
    would mean for a sample row where 'sport_name'='football' and 'sport_time'='13:00'
    the output label would be 'football, 13:00'
    """
    def __init__(self, db_col: str, group: str, fmt_spec, order_col, is_desc: bool):
        super().__init__(db_col, group)
        self.fmt_spec = fmt_spec
        self.order_col = order_col
        self.is_desc = desc

    def get_options(self, db: bdb.BettingDB, db_cte: cte) -> List[List[Any]]:
        """
        get a list of distinct values from database
        """
        if self.is_desc:
            s = desc
        else:
            s = asc
        return db.session.query(db_cte).distinct().order_by(s(db_cte.c[self.db_col])).all()

    def get_labels(self, opts: List[List[Any]]) -> List[Dict[str, Any]]:

        return [{
            'label': self.fmt_spec.format(**dict(row)),
            'value': dict(row)[self.db_col]
        } for row in opts]



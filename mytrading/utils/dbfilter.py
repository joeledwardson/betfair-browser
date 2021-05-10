from typing import Dict, List, Any
from sqlalchemy.engine.row import Row
from sqlalchemy import func, cast, Date, desc, asc, Table
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.sql import cte
from sqlalchemy.sql.expression import ColumnElement
from datetime import date, datetime
from ..exceptions import DBException


class DBFilter:
    """
    database filter for a column of a table
    designed to present a list of options with values that correspond to database value, and labels that can be
    customised for display
    """

    reg: Dict[str, List] = {}

    def __init__(self, db_col: str):
        """
        set db_col to the name of the database column on which it will apply a filter
        """
        self.db_col = db_col
        self.value = None

    def set_value(self, value, clear: bool):
        """
        store value selected by user using 'value', or clear stored value by setting 'clear' to True
        """
        if clear:
            self.value = None
        else:
            self.value = value

    def db_filter(self, tbl: Table) -> ColumnElement:
        """
        return a SQLAlchemy filter of the specified column at initialisation of the table passed as 'tbl' filtered to
        the stored value
        """
        return tbl.columns[self.db_col] == self.value

    def get_options(self, session: Session, tables, db_cte: cte) -> List[Row]:
        """
        get a list of distinct values from database
        """
        return session.query(db_cte.c[self.db_col]).distinct().all()

    def get_labels(self, opts: List[Row]) -> List[Dict[str, Any]]:
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

    def __init__(self, db_col, dt_fmt):
        super().__init__(db_col)
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

    def get_options(self, session: Session, tables, db_cte: cte) -> List[Row]:
        """
        get options starting from most recent date first
        """
        date_col = cast(db_cte.c[self.db_col], Date)
        return session.query(date_col).distinct().order_by(desc(date_col)).all()

    def get_labels(self, opts: List[Row]) -> List[Dict[str, Any]]:
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
    def __init__(self, db_col, join_tbl_name, join_id_col, join_name_col):
        super().__init__(db_col)
        self.join_tbl_name = join_tbl_name
        self.join_id_col = join_id_col
        self.join_name_col = join_name_col
        self.output_col = 'TEMP_OUTPUT_NAME'

    def get_options(self, session: Session, tables, db_cte: cte) -> List[Row]:
        join_tbl = tables[self.join_tbl_name]
        q = session.query(
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

    def get_labels(self, opts: List[Row]) -> List[Dict[str, Any]]:
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
    def __init__(self, db_col: str, fmt_spec, order_col, is_desc: bool, cols: List[str]):
        super().__init__(db_col)
        self.fmt_spec = fmt_spec
        self.order_col = order_col
        self.is_desc = desc if is_desc else asc
        self.cols = cols

    def get_options(self, session: Session, tables, db_cte: cte) -> List[Row]:
        """
        get a list of distinct values from database
        """
        if self.is_desc:
            odr = desc
        else:
            odr = asc
        return session.query(
            *(db_cte.c[col] for col in self.cols)
        ).distinct().order_by(
            odr(db_cte.c[self.order_col])
        ).all()

    def get_labels(self, opts: List[Row]) -> List[Dict[str, Any]]:

        return [{
            'label': self.fmt_spec.format(**dict(row)),
            'value': dict(row)[self.db_col]
        } for row in opts]


class DBFilterText(DBFilter):
    """filter to a text string"""
    NO_OPTIONS = True

    def __init__(self, db_col: str, pre_str='%', post_str='%'):
        super().__init__(db_col)
        self.pre_str = pre_str
        self.post_str = post_str

    def db_filter(self, tbl: Table):
        return tbl.columns[self.db_col].like(f'{self.pre_str}{self.value}{self.post_str}')


class DBFilterHandler:

    def __init__(self, db_filters: List[DBFilter]):
        self._db_filters = db_filters

    def filters_values(self) -> List[Any]:
        return [flt.value for flt in self._db_filters]

    def filters_labels(self, session, tables, cte) -> List[List[Dict[str, Any]]]:
        return [
            flt.get_labels(flt.get_options(session, tables, cte))
            for flt in self._db_filters
            if not hasattr(flt, 'NO_OPTIONS')
        ]

    def update_filters(self, clear, args):
        if len(args) != len(self._db_filters):
            raise DBException(f'args has len {len(args)}, expected {len(self._db_filters)}')
        for val, flt in zip(args, self._db_filters):
            flt.set_value(val, clear)

    def filters_conditions(self, tbl):
        return [
            f.db_filter(tbl)
            for f in self._db_filters if f.value
        ]

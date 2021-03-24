import dash
from dash.dependencies import Output, Input, State
from sqlalchemy import func, cast, Date, desc
from ..data import DashData
from ..tables.files import get_files_table
from myutils.mydash import intermediate
from myutils.mydash.context import triggered_id
from myutils.mydash import context as my_context
from mytrading.utils.bettingdb import BettingDB
import logging
from datetime import date, datetime
from functools import partial

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

# TODO update country codes with country names - see list countries in betfair API https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/listCountries
counter = intermediate.Intermediary()
TABLE_HEADERS = [{
    'db_col': 'betfair_id',
    'name': 'Betfair ID',
}, {
    'db_col': 'market_type',
    'name': 'Market Type',
}, {
    'db_col': 'market_time',
    'name': 'Market Time',
}, {
    'db_col': 'venue',
    'name': 'Venue',
}]
MAX_ROWS = 100
PAGE_SIZE = 8


# max_date = db.session.query(func.max(q.c['market_time'])).scalar()
# min_date = db.session.query(func.min(q.c['market_time'])).scalar()
# dsp_date = None
#
# if max_date:
#     max_date = max_date.date()
#     dsp_date = max_date
#
# if min_date:
#     min_date = min_date.date()

def db_date_fmt(dt: datetime):
    return dt.strftime('%d %b %y')


def db_dt_fmt(dt: datetime):
    return dt.strftime('%Y-%m-%d %H:%M')


def db_distincts(db_col: str, db: BettingDB, cte):
    return db.session.query(cte.c[db_col]).distinct().all()


def db_labels(db_vals, label_func=lambda lbl: lbl):
    return [{
        'label': label_func(v[0]),
        'value': v[0],
    } for v in db_vals]


def db_callback(app: dash.Dash, dd: DashData):
    @app.callback(
        output=[
            Output('input-mkt-type', 'options'),
            Output('input-mkt-type', 'value'),
            Output('input-bet-type', 'options'),
            Output('input-bet-type', 'value'),
            Output('input-country-code', 'options'),
            Output('input-country-code', 'value'),
            Output('input-venue', 'options'),
            Output('input-venue', 'value'),
            Output('input-date', 'options'),
            Output('input-date', 'value'),
            Output('table-market-db', 'data'),
            Output('table-market-db', "selected_cells"),
            Output('table-market-db', 'active_cell'),
        ],
        inputs=[
            Input('input-mkt-type', 'value'),
            Input('input-bet-type', 'value'),
            Input('input-country-code', 'value'),
            Input('input-venue', 'value'),
            Input('input-date', 'value'),
            Input('input-mkt-clear', 'n_clicks'),
            Input('table-market-db', 'sort_mode')
        ],
    )
    def mkt_intermediary(mkt_type, bet_type, cc, venue, date_value, n_clicks, sort_mode):

        conditions = []
        db = dd.betting_db

        # TODO - make intermediary for logger in this file
        if triggered_id() == 'input-mkt-clear':
            active_logger.info('clearing market filters')
            mkt_type, bet_type, cc, venue, date_value = None, None, None, None, None

        if date_value:
            date_value = date.fromisoformat(date_value)
            conditions.append(cast(db.Meta.market_time, Date) == date_value)
        active_logger.info(f'date picked: {date_value}')

        # dict of {database column name: selected value}
        attrs = {
            'market_type': mkt_type,
            'betting_type': bet_type,
            'country_code': cc,
            'venue': venue,
        }
        for db_col, val in attrs.items():
            if val:
                conditions.append(getattr(db.Meta, db_col) == val)

        q = db.session.query(db.Meta).filter(*conditions).cte()

        date_col = cast(q.c.market_time, Date)
        date_options = db.session.query(date_col).distinct().order_by(desc(date_col)).all()

        tbl_funcs = {
            'market_time': db_dt_fmt
        }
        tbl_cols = [q.c[h['db_col']] for h in TABLE_HEADERS]
        q_result = db.session.query(*tbl_cols).limit(MAX_ROWS).all()
        tbl_rows = [dict(r) for r in q_result]
        for row in tbl_rows:
            for k, v in row.items():
                if k in tbl_funcs:
                    row[k] = tbl_funcs[k](v)

        # tbl_rows = [{
        #         k: tbl_funcs.get(k, lambda _: _)(v)
        #         for k, v in dict(r).items()
        #     } for r in q_result
        # ]

        # pad table rows to page size if necessary
        while len(tbl_rows) < PAGE_SIZE:
            tbl_rows.append({})

        _db_distincts = partial(db_distincts, db=db, cte=q)
        return (
            db_labels(_db_distincts('market_type')),
            mkt_type,
            db_labels(_db_distincts('betting_type')),
            bet_type,
            db_labels(_db_distincts('country_code')),
            cc,
            db_labels(_db_distincts('venue')),
            venue,
            db_labels(date_options, label_func=db_date_fmt),
            date_value,
            tbl_rows,
            # clear table selected cells on filter change/clear/sort change
            [],
            None
        )


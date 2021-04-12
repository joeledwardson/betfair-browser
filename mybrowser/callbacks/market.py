from dash.dependencies import Output, Input, State
from myutils.mydash import intermediate
from myutils.mydash import context
import logging

from ..app import app, dash_data as dd
from ..config import config
from ..db import filterobjs as flt
from ..db.filtertypes import DBFilter
from ..db.table import table_out, q_strategy

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

counter = intermediate.Intermediary()


@app.callback(
    output=[
        Output('input-strategy-select', 'options'),
        Output('input-strategy-select', 'value'),
    ],
    inputs=[
        Input('input-strategy-select', 'value'),
        Input('input-strategy-clear', 'n_clicks'),
    ],
)
def strategy_callback(strat_select, n_clicks):
    db = dd.betting_db
    meta = db.tables['strategymeta']
    clear = context.triggered_id() == 'input-strategy-clear'

    flt.strat_id.set_value(strat_select, clear)

    conditions = [f.db_filter(meta) for f in DBFilter.reg['STRATEGYFILTERS'] if f.value]
    q = db.session.query(meta).filter(*conditions)
    cte = q.cte()

    return (
        flt.strat_id.get_labels(flt.strat_id.get_options(db, cte)),
        flt.strat_id.value,
    )


# TODO - expand strategy select inputs
inputs = [
    Input('input-sport-type', 'value'),
    Input('input-mkt-type', 'value'),
    Input('input-bet-type', 'value'),
    Input('input-format', 'value'),
    Input('input-country-code', 'value'),
    Input('input-venue', 'value'),
    Input('input-date', 'value'),

    Input('input-mkt-clear', 'n_clicks'),
    Input('table-market-db', 'sort_mode'),
    Input('input-strategy-select', 'value'),

    # *[Input(k, 'value') for k in market_filters.keys()]
]

outputs = [
    # *[Output(k, 'options') for k in market_filters.keys()],
    # *[Output(k, 'value') for k in market_filters.keys()]

    Output('input-sport-type', 'options'),
    Output('input-sport-type', 'value'),
    Output('input-mkt-type', 'options'),
    Output('input-mkt-type', 'value'),
    Output('input-bet-type', 'options'),
    Output('input-bet-type', 'value'),
    Output('input-format', 'options'),
    Output('input-format', 'value'),
    Output('input-country-code', 'options'),
    Output('input-country-code', 'value'),
    Output('input-venue', 'options'),
    Output('input-venue', 'value'),
    Output('input-date', 'options'),
    Output('input-date', 'value'),
    Output('market-query-status', 'children'),
    Output('table-market-db', 'data'),
    Output('table-market-db', "selected_cells"),
    Output('table-market-db', 'active_cell'),
    Output('table-market-db', 'page_current'),
    Output('loading-out-db', 'children'),
    Output('intermediary-db-market', 'children')
]

states = [
    State('table-market-db', 'active_cell')
]


# TODO - put filters into generic list whose inputs/outputs are automatically expanded and generated
@app.callback(
    output=outputs,
    inputs=inputs,
    state=states,
)
def mkt_intermediary(
        mkt_sport,
        mkt_type,
        mkt_bet,
        mkt_format,
        mkt_country,
        mkt_venue,
        mkt_date,
        n_clicks,
        sort_mode,
        strategy_id,
        active_cell
):

    db = dd.betting_db
    meta = db.tables['marketmeta']

    clear = context.triggered_id() == 'input-mkt-clear'
    flt.mkt_sport.set_value(mkt_sport, clear)
    flt.mkt_type.set_value(mkt_type, clear)
    flt.mkt_bet.set_value(mkt_bet, clear)
    flt.mkt_format.set_value(mkt_format, clear)
    flt.mkt_country.set_value(mkt_country, clear)
    flt.mkt_venue.set_value(mkt_venue, clear)
    flt.mkt_date.set_value(mkt_date, clear)

    active_logger.info(f'active cell: {active_cell}')

    # TODO - split date into year/month/day components
    col_names = list(config['TABLE_COLS'].keys())

    if strategy_id:
        q = q_strategy(strategy_id, db)
        col_names.append('market_profit')
    else:
        q = db.session.query(meta)

    conditions = [f.db_filter(meta) for f in DBFilter.reg['MARKETFILTERS'] if f.value]
    q = q.filter(*conditions)
    n = q.count()
    cte = q.cte()
    cols = [cte.c[nm] for nm in col_names]

    tbl_rows = table_out(
        tbl_cols=cols,
        db=db,
        max_rows=int(config['DB']['max_rows']),
        id_col='market_id',
        fmt_config=config['TABLE_FORMATTERS']
    )
    # tbl_rows = market_table.table_output(cols, db)

    return (
        # sport type input choices and selected value
        flt.mkt_sport.get_labels(flt.mkt_sport.get_options(db, cte)),
        flt.mkt_sport.value,

        # market type input choices and selected value
        flt.mkt_type.get_labels(flt.mkt_type.get_options(db, cte)),
        flt.mkt_type.value,

        # betting type input choices and selected value
        flt.mkt_bet.get_labels(flt.mkt_bet.get_options(db, cte)),
        flt.mkt_bet.value,

        # market format input choices and selected value
        flt.mkt_format.get_labels(flt.mkt_format.get_options(db, cte)),
        flt.mkt_format.value,

        # country input choices and selected value
        flt.mkt_country.get_labels(flt.mkt_country.get_options(db, cte)),
        flt.mkt_country.value,

        # venue input choices and selected value
        flt.mkt_venue.get_labels(flt.mkt_venue.get_options(db, cte)),
        flt.mkt_venue.value,

        # date input choices and selected value
        flt.mkt_date.get_labels(flt.mkt_date.get_options(db, cte)),
        flt.mkt_date.value,

        # table query status
        f'Showing {len(tbl_rows)} of {n} available',

        # set market table row data
        tbl_rows,

        # clear table selected cell(s) & selected cell values
        [],
        None,

        # reset current page back to 0 and set number of pages
        0,

        # loading output
        '',

        # intermediary counter value
        counter.next()
    )


@app.callback(
    Output("right-side-bar", "className"),
    [
        Input("btn-db-filter", "n_clicks"),
        Input("btn-right-close", "n_clicks")
    ],
)
def toggle_classname(n1, n2):
    if context.triggered_id() == 'btn-db-filter':
        return "right-not-collapsed"
    else:
        return ""

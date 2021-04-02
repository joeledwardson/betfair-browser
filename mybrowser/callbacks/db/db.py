from dash.dependencies import Output, Input, State
from myutils.mydash import intermediate
from myutils.mydash.context import triggered_id
from ..globals import IORegister
from ...app import app, dash_data as dd
from sqlalchemy.sql.functions import sum as sql_sum
from .objs import *

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


# TODO update country codes with country names - see list countries in betfair API https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/listCountries
counter = intermediate.Intermediary()


def q_strategy(strategy_id, db):
    """
    get query for marketmeta , filtered to markets for strategy specified with additional "market_profit" column for
    total profit for strategy for given market, grouped over runner profits per market

    Parameters
    ----------
    strategy_id :

    Returns
    -------
    """
    sr = db.tables['strategyrunners']
    meta = db.tables['marketmeta']

    strat_cte = db.session.query(
        sr.columns['market_id'],
        sql_sum(sr.columns['profit']).label('market_profit')
    ).filter(
        sr.columns['strategy_id'] == strategy_id
    ).group_by(
        sr.columns['market_id']
    ).cte()

    return db.session.query(
        meta,
        strat_cte.c['market_profit']
    ).join(
        strat_cte,
        meta.columns['market_id'] == strat_cte.c['market_id']
    )


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
    clear = triggered_id() == 'input-strategy-clear'

    filter_strat_select.set_value(strat_select, clear)

    conditions = [f.db_filter(meta) for f in reg['STRATEGYFILTERS'] if f.value]
    q = db.session.query(meta).filter(*conditions)
    cte = q.cte()

    return (
        filter_strat_select.get_labels(filter_strat_select.get_options(db, cte)),
        filter_strat_select.value,
    )


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

mid = Output('intermediary-db-market', 'children')

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
    mid
]

states = [
    State('table-market-db', 'active_cell')
]

IORegister.register_inputs(inputs)
IORegister.register_mid(mid)


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

    clear = triggered_id() == 'input-mkt-clear'
    filter_sport.set_value(mkt_sport, clear)
    filter_type.set_value(mkt_type, clear)
    filter_bet.set_value(mkt_bet, clear)
    filter_format.set_value(mkt_format, clear)
    filter_country.set_value(mkt_country, clear)
    filter_venue.set_value(mkt_venue, clear)
    filter_date.set_value(mkt_date, clear)

    active_logger.info(f'active cell: {active_cell}')

    # TODO - split date into year/month/day components
    # TODO - make intermediary for logger in this file
    # TODO - query from joined expression filtered to only markets from strategy (if strategy selected)
    col_names = list(config['TABLECOLS'].keys())

    if strategy_id:
        q = q_strategy(strategy_id, db)
        col_names.append('market_profit')
    else:
        q = db.session.query(meta)

    conditions = [f.db_filter(meta) for f in reg['MARKETFILTERS'] if f.value]
    q = q.filter(*conditions)
    n = q.count()
    cte = q.cte()
    cols = [cte.c[nm] for nm in col_names]
    tbl_rows = market_table.table_output(cols, db)

    return (
        # sport type input choices and selected value
        filter_sport.get_labels(filter_sport.get_options(db, cte)),
        filter_sport.value,

        # market type input choices and selected value
        filter_type.get_labels(filter_type.get_options(db, cte)),
        filter_type.value,

        # betting type input choices and selected value
        filter_bet.get_labels(filter_bet.get_options(db, cte)),
        filter_bet.value,

        # market format input choices and selected value
        filter_format.get_labels(filter_format.get_options(db, cte)),
        filter_format.value,

        # country input choices and selected value
        filter_country.get_labels(filter_country.get_options(db, cte)),
        filter_country.value,

        # venue input choices and selected value
        filter_venue.get_labels(filter_venue.get_options(db, cte)),
        filter_venue.value,

        # date input choices and selected value
        filter_date.get_labels(filter_date.get_options(db, cte)),
        filter_date.value,

        # table query status
        f'Showing {len(market_table.q_result)} of {n} available',

        # set market table row data
        tbl_rows,

        # clear table selected cell(s) & selected cell values
        [],
        None,

        # reset current page back to 0 and set number of pages
        0,

        # intermediary counter value
        counter.next()
    )


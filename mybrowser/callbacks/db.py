import dash
from dash.dependencies import Output, Input, State
from ..data import DashData
from ..config import config
from myutils.mydash import intermediate
from myutils.mydash.context import triggered_id
from mytrading.utils.bettingdb import BettingDB
import logging
from datetime import date, datetime
from functools import partial
from ..dbdefs import DateFilter, JoinedFilter, MarketFilter, filters, formatters, table_output

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

filter_sport = JoinedFilter(
    "sport_id",
    join_tbl_name='sportids',
    join_id_col='sport_id',
    join_name_col='sport_name'
)
filter_country = JoinedFilter(
    "country_code",
    join_tbl_name='countrycodes',
    join_id_col='alpha_2_code',
    join_name_col='name'
)
filter_type = MarketFilter("market_type")
filter_bet = MarketFilter("betting_type")
filter_venue = MarketFilter("venue")
filter_date = DateFilter("market_time")


# TODO update country codes with country names - see list countries in betfair API https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/listCountries
counter = intermediate.Intermediary()


def db_callback(app: dash.Dash, dd: DashData):
    @app.callback(
        output=[
            Output('input-sport-type', 'options'),
            Output('input-sport-type', 'value'),
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
            Output('table-market-db', 'page_current'),
        ],
        inputs=[
            Input('input-sport-type', 'value'),
            Input('input-mkt-type', 'value'),
            Input('input-bet-type', 'value'),
            Input('input-country-code', 'value'),
            Input('input-venue', 'value'),
            Input('input-date', 'value'),
            Input('input-mkt-clear', 'n_clicks'),
            Input('table-market-db', 'sort_mode'),
        ],
        state=[
            State('table-market-db', 'active_cell')
        ],
    )
    def mkt_intermediary(sport_type, mkt_type, bet_type, cc, venue, date_value, n_clicks, sort_mode, active_cell):

        db = dd.betting_db
        meta = db.tables['marketmeta']

        clear = triggered_id() == 'input-mkt-clear'
        filter_sport.set_value(sport_type, clear)
        filter_type.set_value(mkt_type, clear)
        filter_bet.set_value(bet_type, clear)
        filter_country.set_value(cc, clear)
        filter_venue.set_value(venue, clear)
        filter_date.set_value(date_value, clear)

        active_logger.info(f'active cell: {active_cell}')

        # TODO - make intermediary for logger in this file
        conditions = [f.db_filter(meta) for f in filters if f.value]
        q = db.session.query(meta).filter(*conditions).cte()
        tbl_rows = table_output(q, db)

        return (
            # sport type input choices and selected value
            filter_sport.get_labels(filter_sport.get_options(db, q)),
            filter_sport.value,

            # market type input choices and selected value
            filter_type.get_labels(filter_type.get_options(db, q)),
            filter_type.value,

            # betting type input choices and selected value
            filter_bet.get_labels(filter_bet.get_options(db, q)),
            filter_bet.value,

            # country input choices and selected value
            filter_country.get_labels(filter_country.get_options(db, q)),
            filter_country.value,

            # venue input choices and selected value
            filter_venue.get_labels(filter_venue.get_options(db, q)),
            filter_venue.value,

            # date input choices and selected value
            filter_date.get_labels(filter_date.get_options(db, q)),
            filter_date.value,

            # set market table row data
            tbl_rows,

            # clear table selected cell(s) & selected cell values
            [],
            None,

            # reset current page back to 0
            0,
        )


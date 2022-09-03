from dataclasses import dataclass
from typing import List, Dict, Callable, Any, Optional
from pydantic import (
    BaseModel,
    BaseSettings,
    Field,
)
from datetime import datetime, timedelta
from mytrading.utils import dbfilter as dbf
from myutils.dashutilities import interface as comp
from . import formatters


@dataclass
class MarketFilter:
    component_id: str
    component: any
    filter: dbf.DBFilter


def get_strategy_filters(date_format: str) -> List[dbf.DBFilter]:
    return [
        dbf.DBFilterMulti(
            'strategy_id',
            fmt_spec=date_format,
            order_col='exec_time',
            is_desc=True,
            cols=['strategy_id', 'exec_time', 'name']
        )
    ]


def get_market_filters(date_format: str) -> List[MarketFilter]:
    id_sport = 'input-sport-type'
    id_market_type = 'input-market-type'
    id_bet_type = 'input-bet-type'
    id_format = 'input-format'
    id_country_code = 'input-country-code'
    id_venue = 'input-venue'
    id_date = 'input-date'
    id_market = 'input-market-id'

    return [
        MarketFilter(
            id_sport,
            comp.select(id_sport, placeholder='Sport...'),
            dbf.DBFilterJoin(
                db_col='sport_id',
                join_tbl_name='sportids',
                join_id_col='sport_id',
                join_name_col='sport_name'
            )
        ),
        MarketFilter(
            id_market_type,
            comp.select(id_market_type, placeholder='Market type...'),
            dbf.DBFilter(db_col='market_type')
        ),
        MarketFilter(
            id_bet_type,
            comp.select(id_bet_type, placeholder='Betting type...'),
            dbf.DBFilter(db_col='betting_type')
        ),
        MarketFilter(
            id_format,
            comp.select(id_format, placeholder='Format...'),
            dbf.DBFilter(db_col='format')
        ),
        MarketFilter(
            id_country_code,
            comp.select(id_country_code, placeholder='Country...'),
            dbf.DBFilterJoin(
                db_col="country_code",
                join_tbl_name='countrycodes',
                join_id_col='alpha_2_code',
                join_name_col='name'
            )
        ),
        MarketFilter(
            id_venue,
            comp.select(id_venue, placeholder='Venue...'),
            dbf.DBFilter(db_col='venue')
        ),
        MarketFilter(
            id_date,
            comp.select(id_date, placeholder='Market date...'),
            dbf.DBFilterDate(
                db_col='market_time',
                dt_fmt=date_format
            )
        ),
        MarketFilter(
            id_market,
            comp.input_component(id_market, placeholder='Market ID filter...'),
            dbf.DBFilterText(db_col='market_id')
        )
    ]


def default_datetime_formatter(value: datetime):
    return formatters.format_datetime(value, "%Y-%m-%d %H:%M")


def default_timedelta_formatter(value: timedelta):
    return formatters.format_timedelta(value, "{d}d {h:02}:{m:02}:{s:02}.{u:06}")


def default_money_formatter(value: Optional[float]):
    return formatters.format_money(value,  "£{value:+.2f}")


class DisplayConfig(BaseModel):
    """
    Dashboard display
    """
    cache: bool = Field(True, description="display interactions for reading/writing to cache")
    libraries: bool = Field(True, description="display interactions for reloading libraries")
    strategy_delete: bool = Field(True, description="display interaction for deleting strategy")
    config_reloads: bool = Field(True, description="display interaction for reloading feature and plot configurations")


class DatabaseConfig(BaseModel):
    """
    Database querying
    """
    market_date_format: str = Field(
        "%d %b %y",
        description="market date format to present in market filter")
    strategy_date_format: str = Field(
        "{exec_time:%y-%m-%d %H:%M:%S} {name}",
        description="strategy datetime format used in strategy filter"
    )
    max_rows: int = Field(100, description="maximum number of rows to return from a database query")
    db_kwargs: Dict[str, Any] = Field(
        {
            'db_lang': 'postgresql',
            'db_user': 'better',
            'db_host': 'joelsnetflix.com',
            'db_port': 5432,
            'db_name': 'betting',
            'db_engine': 'psycopg2',
            'cache_root': 'bf_cache'
        },
        description="kwargs passed when creating BettingDB"
    )


class TableConfigs(BaseModel):
    """
    Tabular displays
    """
    market_rows: int = Field(12, description="number of rows to display in market table")
    strategy_rows: int = Field(12, description="number of rows to display in strategy table")
    runner_rows: int = Field(10, description="number of rows to display in runner table")
    orders_rows: int = Field(15, description="number of rows to display in order table")
    timings_rows: int = Field(15, description="number of rows to display in timings table")

    market_table_cols: dict = Field(
        {
            "market_id": "Market ID",
            "market_type": "Market Type",
            "market_time": "Market Time",
            "venue": "Venue",
            "market_profit": "Profit"
        },
        description="""market column mappings
        maps database column name -> display column title
        n.b. in addition to the database columns, there are calculated columns available:
        -> "market_profit" is calculated from strategy market profit
        """)

    market_sort_options: dict = Field({
        "market_id": "Market ID",
        "market_time": "Market Time"
    })

    market_table_formatters: Dict[str, Callable[[Any], Any]] = Field(
        {
            "market_time": default_datetime_formatter,
            "market_profit": default_money_formatter
        },
        description='mappings of market table column name to formatter function'
    )

    strategy_table_cols: dict = Field(
        {
            'strategy_id': 'Strategy ID',
            'type': 'Type',
            'name': 'Name',
            'exec_time': 'Execution Time',
            'date_added': 'Date Added',
            'n_markets': 'Market Count',
            'total_profit': 'Total Profit'
        },
        description="""strategy column mappings
        maps database column name -> display column title
        n.b. in addition to the database columns, there are calculated columns available:
        -> "n_markets" is the total markets available for the strategy
        -> "total_profit" is the calculated total profit for the strategy
        """)

    strategy_table_formatters: Dict[str, Callable[[Any], Any]] = Field(
        {
            'exec_time': default_datetime_formatter,
            'date_added': default_datetime_formatter,
            'total_profit': default_money_formatter
        },
        description='mappings of strategy table column name to formatter function'
    )

    runner_table_cols: dict = Field(
        {
            'runner_id': 'Selection ID',
            'runner_name': 'Name',
            'starting_odds': 'Starting Odds',
            'runner_profit': 'Profit'
        },
        description="""runner column mappings
        maps database column name -> display column title
        n.b. in addition to the database columns, there are calculated columns available:
        -> "starting_odds" is the odds of the runner at the start of the race
        -> "runner_profit" is the profit on the runner from the selected strategy
        """
    )

    runner_table_formatters: Dict[str, Callable[[Any], Any]] = Field(
        {
            'runner_profit': default_money_formatter,
        },
        description='mappings of runner table column name to formatter function'
    )

    timings_table_cols: dict = Field(
        {
            'function': 'Function',
            'count': 'Count',
            'mean': 'Mean',
            'level': 'Level'
        },
        description="""timings table mappings
        maps timing attribute -> display column title
        timing attributes are from TimingRegistrar.get_timings_summary()
        """
    )

    timings_table_formatters: Dict[str, Callable[[Any], Any]] = Field(
        {
            "mean": default_timedelta_formatter
        },
        description='mappings of timings table column name to formatter function'
    )

    order_table_cols: dict = Field(
        {
            'date': 'Timestamp',
            'trade': 'Trade Index',
            'side': 'Side',
            'price': 'Price',
            'size': 'Size',
            'm-price': 'Matched Price',
            'matched': 'Matched',
            'order-profit': 'Order',
            'trade-profit': 'Trade',
            't-start': 'Time to Start'
        },
        description="""order table mappings
        maps order attribute -> display column title
        """)


class PlotConfig(BaseModel):
    """
    Chart plotting
    """
    default_offset: str = Field("00:03:00", description="default time offset before start of event")
    order_offset_secs: int = Field(2, description="number of seconds to plot either side of order update start/end")
    cmp_buffer_secs: int = Field(10, description="additional seconds to add when computing features for plotting")


class Config(BaseSettings):
    display_config: DisplayConfig = DisplayConfig()
    database_config: DatabaseConfig = DatabaseConfig()
    table_configs: TableConfigs = TableConfigs()
    plot_config: PlotConfig = PlotConfig()

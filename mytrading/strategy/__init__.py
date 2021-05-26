from typing import Dict, Optional, Callable
import yaml
import logging
from myutils import myregistrar as myreg
from myutils import mydict
from uuid import UUID
from ..exceptions import MyStrategyException
from ..utils import BettingDB
from .strategy import BackTestClientNoMin, MyFeatureStrategy
from flumine import FlumineBacktest, clients, Flumine
from betfairlightweight.filters import streaming_market_filter, streaming_market_data_filter
from betfairlightweight import APIClient

strategies_reg = myreg.MyRegistrar()
active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class MyBetfairClient(clients.BetfairClient):
    @property
    def min_bet_size(self) -> Optional[float]:
        """
        no minimum bet size (this should only be used for greening, not placing orders)
        """
        return 0


STRATEGY_CONFIG_SPEC = {
    'name': {
        'type': str,
    },
    'info': {
        'type': dict,
    },
    'market_filter_spec': {
        'type': list,
    }
}

ALL_MARKET_DATA_FILTER = streaming_market_data_filter(fields=[
    "EX_BEST_OFFERS_DISP",
    "EX_BEST_OFFERS",
    "EX_ALL_OFFERS",
    "EX_TRADED",
    "EX_TRADED_VOL",
    "EX_LTP",
    "EX_MARKET_DEF",
    "SP_TRADED",
    "SP_PROJECTED"
])


def _gen_strat(nm: str, kwargs: Dict) -> MyFeatureStrategy:
    try:
        strategy_obj = strategies_reg[nm](**kwargs)
    except TypeError as e:
        raise MyStrategyException(f'could not create strategy "{nm}": "{e}"')
    strategy_obj.strategy_write_info(kwargs)
    active_logger.info(f'creating strategy "{nm}" with args:\n'
                       f'{yaml.dump(kwargs, sort_keys=False)}')
    return strategy_obj


def hist_strat_create(cfg: Dict, db: BettingDB) -> MyFeatureStrategy:
    mydict.validate_config(cfg, STRATEGY_CONFIG_SPEC)
    nm = cfg['name']
    kwargs = cfg['info']
    filter_spec = cfg['market_filter_spec']
    paths = db.paths_market_updates(filter_spec=filter_spec)
    kwargs['historic'] = True
    kwargs['market_filter'] = {
        'markets': paths
    }
    strategy_obj = _gen_strat(nm, kwargs)
    return strategy_obj


def hist_strat_run(strategy_obj: MyFeatureStrategy):
    client = BackTestClientNoMin(transaction_limit=None)
    framework = FlumineBacktest(client=client)
    framework.add_strategy(strategy_obj)
    framework.run()


# TODO - make this work by getting catalogues
def live_strat_create(cfg: Dict) -> MyFeatureStrategy:
    mydict.validate_config(cfg, STRATEGY_CONFIG_SPEC)
    nm = cfg['name']
    kwargs = cfg['info']
    filter_spec = cfg['market_filter_spec']
    kwargs['historic'] = False
    kwargs['market_filter'] = streaming_market_filter(**filter_spec)
    kwargs['market_data_filter'] = ALL_MARKET_DATA_FILTER
    strategy_obj = _gen_strat(nm, kwargs)
    return strategy_obj


def live_strat_run(strategy_obj: MyFeatureStrategy, trading: APIClient):
    client = MyBetfairClient(trading)
    framework = Flumine(client=client)
    framework.add_strategy(strategy_obj)
    framework.run()


from typing import Dict
import yaml
import logging
from myutils import myregistrar as myreg
from myutils import mydict
from uuid import UUID
from ..exceptions import MyStrategyException
from ..utils import BettingDB
from .strategy import BackTestClientNoMin, MyFeatureStrategy
from flumine import FlumineBacktest
from betfairlightweight.filters import streaming_market_filter


strategies_reg = myreg.MyRegistrar()
active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

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
    try:
        strategy_obj = strategies_reg[nm](**kwargs)
    except TypeError as e:
        raise MyStrategyException(f'could not create strategy "{nm}": "{e}"')
    strategy_obj.strategy_write_info(kwargs)
    active_logger.info(f'creating strategy "{nm}" with args:\n'
                       f'{yaml.dump(kwargs, sort_keys=False)}')
    return strategy_obj


def hist_strat_run(strategy_obj: MyFeatureStrategy):
    client = BackTestClientNoMin(transaction_limit=None)
    framework = FlumineBacktest(client=client)
    framework.add_strategy(strategy_obj)
    framework.run()




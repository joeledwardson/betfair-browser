from typing import Dict
import yaml
import logging
from myutils import myregistrar as myreg
from myutils import mydict
from ..exceptions import MyStrategyException
from ..utils import BettingDB
from .strategy import BackTestClientNoMin
from flumine import FlumineBacktest

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


def run_strategy(cfg: Dict, historic: bool, db: BettingDB) -> float:
    mydict.validate_config(cfg, STRATEGY_CONFIG_SPEC)
    nm = cfg['name']
    kwargs = cfg['info']
    filter_spec = cfg['market_filter_spec']
    paths = db.paths_market_updates(filter_spec=filter_spec)
    kwargs['historic'] = historic
    kwargs['market_filter'] = {
        'markets': paths
    }
    try:
        strategy_obj = strategies_reg[nm](**kwargs)
    except TypeError as e:
        raise MyStrategyException(f'could not create strategy "{nm}": "{e}"')
    strategy_obj.strategy_write_info(kwargs)
    active_logger.info(f'running strategy "{nm}" with args:\n'
                       f'{yaml.dump(kwargs, sort_keys=False)}')

    client = BackTestClientNoMin(transaction_limit=None)
    framework = FlumineBacktest(client=client)
    framework.add_strategy(strategy_obj)
    framework.run()

    total_profit = 0
    for market in framework.markets:
        market_profit = sum(o.simulated.profit for o in market.blotter)
        total_profit += market_profit
    return total_profit


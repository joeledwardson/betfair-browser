"""
original strategy utils, before the statemachine for strategy implementations was created
"""
from flumine import BaseStrategy
from flumine.order.order import BaseOrder, LimitOrder
from flumine.order.trade import Trade
from flumine.order.order import OrderStatus
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import RunnerBook

import logging
from typing import List


active_logger = logging.getLogger(__name__)


def filter_orders(orders, selection_id) -> List[BaseOrder]:
    """
    filter order to those placed on a specific runner identified by `selection_id`
    """
    return [o for o in orders if o.selection_id == selection_id]

def filter_orders(orders, selection_id) -> List[BaseOrder]:
    """
    filter order to those placed on a specific runner identified by `selection_id`
    """
    return [o for o in orders if o.selection_id == selection_id]


# lay if below bookmaker price
def lay_low(
        strategy: BaseStrategy,
        runner: RunnerBook,
        market: Market,
        bookie_odds: float,
        stake_size):

    # d = market.mydat
    # TODO - implement check for runner in oddschecker dataframe
    # if runner.selection_id not in list(d['oc_df'].index)
    # orders = market.blotter._orders.values()

    # check if runner ID not found in oddschecker list, or already has an order
    if  not(filter_orders(market.blotter, runner.selection_id)):
        return

    atl = runner.ex.available_to_lay
    if not atl:
        return

    price = atl[0]['price']
    size = atl[0]['size']

    if not float(price) < float(bookie_odds):
        return

    if price < 1:
        return

    active_logger.info(f'runner id "{runner.selection_id}" best atl {price} for £{size:.2f}, bookie avg is'
                       f' {bookie_odds}')

    trade = Trade(
        market_id=market.market_id,
        selection_id=runner.selection_id,
        handicap=runner.handicap,
        strategy=strategy)
    lay_order = trade.create_order(
        side='LAY',
        order_type=LimitOrder(
            price=price,
            size=stake_size
        ))
    strategy.place_order(market, lay_order)


# back if above back_scale*bookie_odds
def back_high(
        strategy: BaseStrategy,
        runner: RunnerBook,
        market: Market,
        back_scale,
        bookie_odds: float,
        stake_size):

    # orders = market.blotter._orders.values()

    # check if runner ID not found in oddschecker list, or already has an order
    if  not(filter_orders(market.blotter, runner.selection_id)):
        return

    atb = runner.ex.available_to_back
    if not atb:
        return

    price = atb[0]['price']
    size = atb[0]['size']

    if price < 1:
        return

    if not float(price) > back_scale * float(bookie_odds):
        return

    active_logger.info(f'runner id "{runner.selection_id}" best atb {price} for £{size}, bookie max is {bookie_odds}')

    trade = Trade(
        market_id=market.market_id,
        selection_id=runner.selection_id,
        handicap=runner.handicap,
        strategy=strategy)
    back_order = trade.create_order(
        side='BACK',
        order_type=LimitOrder(
            price=price,
            size=stake_size
        ))
    strategy.place_order(market, back_order)


# cancel an order if unmatched after 'wait_complete_seconds'
def cancel_unmatched(
        order: BaseOrder,
        wait_complete_seconds=2.0):
    if order.status != OrderStatus.EXECUTION_COMPLETE:
        if order.elapsed_seconds >= wait_complete_seconds:
            active_logger.info('cancelling order on "{0}", {1} £{2:.2f} at {3}'.format(
                order.selection_id,
                order.side,
                order.order_type.size,
                order.order_type.price
            ))
            order.cancel()


# green a runner - runner's active orders will be left to complete for 'wait_complete_seconds', and minimum exposure
# to require greening is 'min_green_pence'
def green_runner(
        strategy: BaseStrategy,
        runner: RunnerBook,
        market: Market,
        wait_complete_seconds=2.0,
        min_green_pence=10):

    orders = filter_orders(market.blotter, runner.selection_id)

    if not orders:
        return

    # check all orders for runner have been given at least minimum time to process
    if not all([o for o in orders if o.elapsed_seconds >= wait_complete_seconds]):
        active_logger.debug(f'waiting for orders on "{runner.selection_id}" to exceed {wait_complete_seconds} seconds')
        return

    active_logger.debug(f'attempting to green "{runner.selection_id}"')

    back_profit = sum([
        (o.average_price_matched - 1 or 0)*(o.size_matched or 0) for o in orders
        if o.status==OrderStatus.EXECUTABLE or o.status==OrderStatus.EXECUTION_COMPLETE
           and o.side=='BACK'])
    lay_exposure = sum([
        (o.average_price_matched - 1 or 0)*(o.size_matched or 0) for o in orders
        if o.status==OrderStatus.EXECUTABLE or o.status==OrderStatus.EXECUTION_COMPLETE
           and o.side=='LAY'])

    outstanding_profit = back_profit - lay_exposure
    active_logger.debug(f'runner has £{back_profit:.2f} back profit and £{lay_exposure:.2f}')

    if not abs(outstanding_profit) > min_green_pence:
        return

    if outstanding_profit > 0:
        side = 'LAY'
        available = runner.ex.available_to_lay
        if not available:
            active_logger.debug('no lay options to green')
            return
    else:
        side = 'BACK'
        available = runner.ex.available_to_back
        if not available:
            active_logger.debug('no back options to green')
            return

    green_price = available[0]['price']
    green_size = round(abs(outstanding_profit) / (green_price - 1), 2)

    active_logger.info('greening active order on "{}", £{} at {}'.format(
        runner.selection_id,
        green_size,
        green_price,
    ))
    trade = Trade(
        market_id=market.market_id,
        selection_id=runner.selection_id,
        handicap=runner.handicap,
        strategy=strategy)
    green_order = trade.create_order(
        side=side,
        order_type=LimitOrder(
            price=green_price,
            size=green_size
        ))
    strategy.place_order(market, green_order)

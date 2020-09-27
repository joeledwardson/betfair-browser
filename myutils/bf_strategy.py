from flumine import FlumineBacktest, clients, BaseStrategy
from flumine.order.order import BaseOrder, BetfairOrder, OrderStatus
from flumine.order.trade import Trade
from flumine.order.ordertype import LimitOrder
from flumine.markets.market import Market
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook, MarketCatalogue
from betfairlightweight import APIClient

import json
from myutils import betting, generic
from myutils import bf_feature as bff, bf_window as bfw, bf_trademachine as bftm, statemachine as stm
from myutils import bf_utils as bfu
from myutils.generic import  i_prev, i_next
import os
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import statistics
import statsmodels.api as sm
import operator
from enum import Enum
from dataclasses import dataclass
from dataclasses import dataclass, field
import operator

active_logger = logging.getLogger(__name__)


# filter orders to runner
def filter_orders(orders, selection_id) -> List[BaseOrder]:
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


class MyBaseStrategy(BaseStrategy):

    def check_market_book(self, market, market_book):
        # process_market_book only executed if this returns True
        if market_book.status != "CLOSED":
            return True

    # override default place order, this time printing where order validation failed
    # TODO - print reason for validation fail
    def place_order(self, market, order) -> None:
        runner_context = self.get_runner_context(*order.lookup)
        if self.validate_order(runner_context, order):
            runner_context.place()
            market.place_order(order)
        else:
            active_logger.warning(f'order validation failed for "{order.selection_id}"')


class BackTestClientNoMin(clients.BacktestClient):
    @property
    def min_bet_size(self) -> Optional[float]:
        return 0




class MyFeatureData:
    def __init__(self, market_book: MarketBook):
        self.windows: bfw.Windows = bfw.Windows()
        self.features: Dict[int, Dict[str, bff.RunnerFeatureBase]] = {
            runner.selection_id: bff.get_default_features(
                runner.selection_id,
                market_book,
                self.windows
            ) for runner in market_book.runners
        }
        self.market_books: List[MarketBook] = []


class MyFeatureStrategy(MyBaseStrategy):

    def __init__(self, *kargs, **kwargs):
        super().__init__(*kargs, **kwargs)

        # feature data, indexed by market ID
        self.feature_data: [Dict, MyFeatureData] = dict()

    def create_feature_data(self, market: Market, market_book: MarketBook) -> MyFeatureData:
        return MyFeatureData(market_book)

    # called first time strategy receives a new market
    def market_initialisation(self, market: Market, market_book: MarketBook, feature_data: MyFeatureData):
        pass

    def do_feature_processing(self, feature_data: MyFeatureData, market_book: MarketBook):

        # loop runners
        for runner_index, runner in enumerate(market_book.runners):

            # process each feature for current runner
            for feature in feature_data.features[runner.selection_id].values():
                feature.process_runner(
                    feature_data.market_books,
                    market_book,
                    feature_data.windows,
                    runner_index
                )

    def process_get_feature_data(self, market: Market, market_book: MarketBook) -> MyFeatureData:

        # check if market has been initialised
        if market.market_id not in self.feature_data:
            feature_data = self.create_feature_data(market, market_book)
            self.feature_data[market.market_id] = feature_data
            self.market_initialisation(market, market_book, feature_data)

        # get feature data instance for current market
        feature_data = self.feature_data[market.market_id]

        # if runner doesnt have an element in features dict then add (this must be done before window processing!)
        for runner in market_book.runners:
            if runner.selection_id not in feature_data.features:

                runner_features = bff.get_default_features(
                    selection_id=runner.selection_id,
                    book=market_book,
                    windows=feature_data.windows
                )

                feature_data.features[runner.selection_id] = runner_features

        # append new market book to list
        feature_data.market_books.append(market_book)

        # update windows
        feature_data.windows.update_windows(feature_data.market_books, market_book)

        # process features
        self.do_feature_processing(feature_data, market_book)

        return feature_data



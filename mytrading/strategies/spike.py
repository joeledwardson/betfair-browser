"""
Trade based on back/lay/ltp trend using regression
"""
from enum import Enum
from datetime import datetime
from typing import Dict, Optional
from flumine.order.order import BetfairOrder
from betfairlightweight.resources.bettingresources import RunnerBook
from dataclasses import dataclass
from betfairlightweight.resources import MarketBook
from flumine.markets.market import Market
from flumine.order.order import OrderStatus
from flumine.order.ordertype import LimitOrder, OrderTypes
from functools import partial

from ..configs import feature_configs_spike
from ..process import closest_tick, tick_spread, LTICKS_DECODED
from mytrading.strategy.messages import register_formatter, MessageTypes as BaseMessageTypes
from ..strategy.runnerhandler import RunnerHandler
from ..strategy import tradestates as basestates
from ..strategy.trademachine import RunnerTradeMachine
from ..strategy.strategy import MyFeatureStrategy
from ..strategy.feature import FeatureHolder
from ..strategy.tradetracker import TradeTracker
from ..strategy import strategies_reg
from ..process import get_ltps

MIN_BET_AMOUNT = 2


class SpikeStateTypes(Enum):
    SPIKE_STATE_MONITOR = 'monitor window orders'


@dataclass
class SpikeData:
    best_back: float = 0
    best_lay: float = 0
    spread: int = 0
    ltp: float = 0
    ltp_min: float = 0
    ltp_max: float = 0
    ltp_tick_spread: float = 0

    def validate_spike_data(self):
        return(
                self.best_back and
                self.best_lay and
                self.spread and
                self.ltp and
                self.ltp_min and
                self.ltp_max and
                self.ltp_tick_spread
        )


class SpikeMessageTypes(Enum):
    SPIKE_MSG_START = 'achieved spike criteria'
    SPIKE_MSG_VAL_FAIL = 'failed to validate spike data'
    SPIKE_MSG_CREATE = 'place opening window trades'
    SPIKE_MSG_PRICE_REPLACE = 'replacing price'
    SPIKE_MSG_BREACHED = 'spike reached'
    SPIKE_MSG_SPREAD_FAIL = 'spread validation fail'
    SPIKE_MSG_PERIODIC = 'periodic update'


class SpikeRunnerHandler(RunnerHandler):
    def __init__(
            self,
            selection_id: int,
            trade_tracker: TradeTracker,
            trade_machine,
            features: FeatureHolder
    ):
        super().__init__(selection_id, trade_tracker, trade_machine, features)

        # back and lay orders
        self.back_order: Optional[BetfairOrder] = None
        self.lay_order: Optional[BetfairOrder] = None

        # side of book which spike order has money matched
        self.side_matched: str = ''

        # track previous state minimum/max odds of which offset applied to place spike orders
        self.prev_boundary_top_tick: int = 0
        self.prev_boundary_bottom_tick: int = 0

        self.first_runner: bool = False
        self.spike_data = SpikeData()
        

@strategies_reg.register_element
class MySpikeStrategy(MyFeatureStrategy):
    """
    Trades spikes above & below LTP window max and minimums
    """
    def __init__(
            self,
            *,
            trade_transactions_cutoff: int,
            stake_size: float,
            max_odds: float,
            min_hedge_price: float,
            window_spread_min: int,
            ladder_spread_max: int,
            tick_offset: int,
            tick_trigger: int,
            update_s: float,
            spike_wait_ms: int,
            hedge_tick_offset: int,
            hedge_hold_ms: int,
            features_kwargs: dict,
            enable_lay: bool,
            **kwargs
    ):

        super().__init__(**kwargs)
        self.trade_transactions_cutoff = trade_transactions_cutoff
        self.stake_size = stake_size
        self.max_odds = max_odds
        self.min_hedge_price = min_hedge_price
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max
        self.tick_offset = tick_offset
        self.tick_trigger = tick_trigger
        self.update_s = update_s
        self.spike_wait_ms = spike_wait_ms
        self.hedge_tick_offset = hedge_tick_offset
        self.hedge_hold_ms = hedge_hold_ms
        self.enable_lay = enable_lay

        # generate feature configuration dict
        self.features_config: dict = feature_configs_spike(**features_kwargs)

    def _feature_holder_create(
            self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int
    ) -> FeatureHolder:
        return FeatureHolder.generator(self.features_config)

    def _runner_handler_create(
            self,
            runner_book: RunnerBook,
            feature_holder: FeatureHolder,
            update_path: str,
            trade_machine: RunnerTradeMachine,
            market_id: str
    ) -> RunnerHandler:
        """create runner handler instance on new runner"""
        return SpikeRunnerHandler(
            selection_id=runner_book.selection_id,
            trade_tracker=TradeTracker(
                selection_id=runner_book.selection_id,
                strategy=self,
                market_id=market_id,
                file_path=update_path
            ),
            trade_machine=trade_machine,
            features=feature_holder
        )

    def _trade_machine_create(
            self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int
    ) -> RunnerTradeMachine:
        return RunnerTradeMachine(
            states={
                state.name: state
                for state in [
                    basestates.TradeStateCreateTrade(),
                    SpikeTradeStateIdle(
                        trade_transactions_cutoff=self.trade_transactions_cutoff,
                        max_odds=self.max_odds,
                        window_spread_min=self.window_spread_min,
                        ladder_spread_max=self.ladder_spread_max,
                        next_state=SpikeStateTypes.SPIKE_STATE_MONITOR,
                    ),
                    SpikeTradeStateMonitorWindows(
                        tick_offset=self.tick_offset,
                        tick_trigger=self.tick_trigger,
                        stake_size=self.stake_size,
                        window_spread_min=self.window_spread_min,
                        ladder_spread_max=self.ladder_spread_max,
                        update_s=self.update_s,
                        enable_lay=self.enable_lay,
                        name=SpikeStateTypes.SPIKE_STATE_MONITOR,
                        next_state=[
                            basestates.TradeStateTypes.BIN,
                            basestates.TradeStateTypes.WAIT,
                            basestates.TradeStateTypes.HEDGE_SELECT,
                        ]
                    ),
                    basestates.TradeStateWait(
                        wait_ms=self.spike_wait_ms,
                    ),
                    basestates.TradeStateHedgeSelect(
                        next_state=basestates.TradeStateTypes.HEDGE_QUEUE_PLACE,
                    ),
                    basestates.TradeStateHedgePlaceQueue(
                        tick_offset=self.hedge_tick_offset,
                        min_hedge_price=self.min_hedge_price,
                    ),
                    basestates.TradeStateHedgeWaitQueue(
                        hold_time_ms=self.hedge_hold_ms,
                        hedge_place_state=basestates.TradeStateTypes.HEDGE_QUEUE_PLACE,
                    ),
                    basestates.TradeStateHedgePlaceTake(
                        min_hedge_price=self.min_hedge_price,
                    ),
                    basestates.TradeStateHedgeWaitTake(
                        hedge_place_state=basestates.TradeStateTypes.HEDGE_TAKE_PLACE,
                    ),
                    basestates.TradeStateBin(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStatePending(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStateClean(),
                ]
            },
            initial_state=basestates.TradeStateCreateTrade.name,
            selection_id=rbk.selection_id,
        )

    def _trade_machine_run(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int):
        rh: SpikeRunnerHandler = self.market_handlers[mkt.market_id].runner_handlers[rbk.selection_id]
        # get ID for shortest runner from LTPs
        ltps = get_ltps(mbk)
        rh.spike_data.ltp_max = rh.features['tvlad'].sub_features['dif'].sub_features['max'].last_value()
        rh.spike_data.ltp_min = rh.features['tvlad'].sub_features['dif'].sub_features['min'].last_value()
        rh.spike_data.ltp_tick_spread = rh.features['tvlad'].sub_features['dif'].sub_features['spread'].last_value()
        rh.spike_data.spread = rh.features['spread'].sub_features['smp'].sub_features['avg'].last_value()
        rh.spike_data.ltp = rh.features['ltp'].last_value()
        rh.spike_data.best_back = rh.features['best back'].last_value()
        rh.spike_data.best_lay = rh.features['best lay'].last_value()
        rh.first_runner = next(iter(ltps.keys()), 0)
        rh.trade_machine.run(market=mkt, runner_index=runner_index, runner_handler=rh)


class SpikeTradeStateIdle(basestates.TradeStateIdle):
    def __init__(
            self,
            window_spread_min: int,
            ladder_spread_max: int,
            max_odds: float,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max
        self.max_odds = max_odds

    def trade_criteria(self, market: Market, runner_index: int, runner_handler: SpikeRunnerHandler) -> bool:
        spike_data = runner_handler.spike_data
        trade_tracker = runner_handler.trade_tracker
        market_book = market.market_book

        if not runner_handler.first_runner:
            return False

        if not spike_data.validate_spike_data():
            return False

        if not (spike_data.best_lay <= self.max_odds and spike_data.best_back <= self.max_odds):
            return False

        window_spread = spike_data.ltp_tick_spread
        ladder_spread = spike_data.spread

        if ladder_spread <= self.ladder_spread_max and window_spread >= self.window_spread_min:
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_START,
                dt=market_book.publish_time,
                msg_attrs={
                    'best_back': spike_data.best_back,
                    'best_lay': spike_data.best_lay,
                    'ladder_spread': ladder_spread,
                    'ladder_spread_max': self.ladder_spread_max,
                    'ltp': spike_data.ltp,
                    'ltp_max': spike_data.ltp_max,
                    'ltp_min': spike_data.ltp_min,
                    'window_spread': window_spread,
                    'window_spread_min': self.window_spread_min,
                },
                display_odds=spike_data.ltp,
            )
            return True


class SpikeTradeStateMonitorWindows(basestates.TradeStateBase):
    """
    place opening back/lay orders on entering, change if price moves and cancel & move to hedging if any of either
    trade is matched
    """
    def __init__(
            self,
            tick_offset: int,
            tick_trigger: int,
            stake_size: float,
            ladder_spread_max: int,
            window_spread_min: int,
            update_s: float,
            enable_lay: bool,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.tick_offset = tick_offset
        self.tick_trigger = tick_trigger
        self.stake_size = stake_size
        self.window_spread_min = window_spread_min
        self.ladder_spread_max = ladder_spread_max
        self.update_s = update_s
        self.update_timestamp = datetime.now()
        self.enable_lay = enable_lay

        self.pending_cancel_back = False
        self.pending_cancel_lay = False

    def enter(self, market: Market, runner_index: int, runner_handler: SpikeRunnerHandler):
        market_book = market.market_book
        runner_handler.back_order = None
        runner_handler.lay_order = None
        self.update_timestamp = market_book.publish_time

        self.pending_cancel_back = False
        self.pending_cancel_lay = False

    def _place_window_order(
            self, side: str, runner_handler: SpikeRunnerHandler, price: float, market: Market
    ) -> BetfairOrder:
        trade_tracker = runner_handler.trade_tracker
        market_book = market.market_book

        order = trade_tracker.active_trade.create_order(
            side=side,
            order_type=LimitOrder(
                price=price,
                size=self.stake_size
            )
        )
        trade_tracker.log_update(
            msg_type=SpikeMessageTypes.SPIKE_MSG_CREATE,
            dt=market_book.publish_time,
            msg_attrs={
                'side': side,
                'price': price,
                'size': self.stake_size,
                'order_id': order.id,
            },
            display_odds=price
        )
        market.place_order(order)
        return order

    def _log_msg_replace(
            self, trade_tracker: TradeTracker, publish_time: datetime, side, old_price, new_price, order_id
    ):
        trade_tracker.log_update(
            msg_type=SpikeMessageTypes.SPIKE_MSG_PRICE_REPLACE,
            dt=publish_time,
            msg_attrs={
                'side': side,
                'old_price': old_price,
                'new_price': new_price,
                'order_id': order_id,
            },
            display_odds=new_price,
        )

    def _process_breach(self, runner_handler: SpikeRunnerHandler, market: Market) -> bool:
        trade_tracker = runner_handler.trade_tracker
        market_book = market.market_book
        spike_data = runner_handler.spike_data

        # check if any money has been matched on either back or lay spike orders
        breach = False
        old_tick = 0

        if any([
            o.size_matched > 0 for o in trade_tracker.active_trade.orders
            if o.order_type.ORDER_TYPE == OrderTypes.LIMIT and o.side == 'BACK'
        ]):
            # BACK side matched indicator for hedging state to read
            runner_handler.side_matched = 'BACK'
            # get previous tick from BACK side
            old_tick = runner_handler.prev_boundary_top_tick
            breach = True

        elif any([
            o.size_matched > 0 for o in trade_tracker.active_trade.orders
            if o.order_type.ORDER_TYPE == OrderTypes.LIMIT and o.side == 'LAY'
        ]):
            # LAY side matched indicator for hedging state to read
            runner_handler.side_matched = 'LAY'
            # get previous tick from LAY side
            old_tick = runner_handler.prev_boundary_bottom_tick
            breach = True

        if breach:
            # record tick difference
            ltp_tick = closest_tick(spike_data.ltp, return_index=True)
            tick_diff = ltp_tick - old_tick if old_tick else -1

            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_BREACHED,
                dt=market_book.publish_time,
                msg_attrs={
                    'side': runner_handler.side_matched,
                    'old_price': LTICKS_DECODED[old_tick],
                    'ltp': spike_data.ltp,
                    'spike_ticks': tick_diff
                }
            )
        return breach

    def _cancel(self, rh: RunnerHandler, order_nm: str, mkt: Market, side: str, price, new_price):
        order = getattr(rh, order_nm)
        if order.bet_id is None:
            rh.trade_tracker.log_update(
                msg_type=BaseMessageTypes.MSG_CANCEL_ID_FAIL,
                dt=mkt.market_book.publish_time,
                msg_attrs={
                    'order_id': order.id,
                }
            )
            return True
        else:
            self._log_msg_replace(rh.trade_tracker, mkt.market_book.publish_time,
                                  side=side,
                                  old_price=price,
                                  new_price=new_price,
                                  order_id=order.id)
            mkt.cancel_order(order)
            setattr(rh, order_nm, None)
            return False

    def run(self, market: Market, runner_index: int, runner_handler: SpikeRunnerHandler):
        spike_data = runner_handler.spike_data
        trade_tracker = runner_handler.trade_tracker
        market_book = market.market_book

        # check back/lay/ltp values are all non-null
        if not spike_data.validate_spike_data():
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_VAL_FAIL,
                dt=market_book.publish_time,
                msg_attrs=spike_data.__dict__,
            )
            return [
                basestates.TradeStateTypes.BIN,
                basestates.TradeStateTypes.IDLE,
            ]

        # compute max/min boundary values
        boundary_top_value = max(spike_data.ltp, spike_data.best_back, spike_data.best_lay)  # max of back/lay/ltp
        boundary_top_tick = closest_tick(boundary_top_value, return_index=True)
        top_tick = min(len(LTICKS_DECODED) - 1, boundary_top_tick + self.tick_offset)
        top_value = LTICKS_DECODED[top_tick]  # top of window with margin

        boundary_bottom_value = min(spike_data.ltp, spike_data.best_back, spike_data.best_lay)  # min of back/lay/ltp
        boundary_bottom_tick = closest_tick(boundary_bottom_value, return_index=True)
        bottom_tick = max(0, boundary_bottom_tick - self.tick_offset)
        bottom_value = LTICKS_DECODED[bottom_tick]  # bottom of window with margin

        # check if breached window
        if self._process_breach(runner_handler, market):
            return self.next_state

        # TODO - check ladder spread?
        # check back/lay spread is still within tolerance and ltp min/max spread is above tolerance
        if not(0 <= self.ladder_spread_max and spike_data.ltp_tick_spread >= self.window_spread_min):
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_SPREAD_FAIL,
                dt=market_book.publish_time,
                msg_attrs={
                    'ladder_spread': spike_data.spread,
                    'ladder_spread_max': self.ladder_spread_max,
                    'window_spread': spike_data.ltp_tick_spread,
                    'window_spread_min': self.window_spread_min,
                }
            )
            return [
                basestates.TradeStateTypes.BIN,
                basestates.TradeStateTypes.IDLE,
            ]

        # create back order  if doesn't exist
        if runner_handler.back_order is None:
            runner_handler.back_order = self._place_window_order('BACK', runner_handler, top_value, market)

        # create lay order if doesn't exist
        if runner_handler.lay_order is None and self.enable_lay:
            runner_handler.lay_order = self._place_window_order('LAY', runner_handler, bottom_value, market)

        # check if need periodic update
        if (market_book.publish_time - self.update_timestamp).total_seconds() >= self.update_s:
            self.update_timestamp = market_book.publish_time
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_PERIODIC,
                dt=market_book.publish_time,
                msg_attrs={'periodic_s': self.update_s}
            )
            periodic_update = True
        else:
            periodic_update = False

        # cancel back order if price moved so can be replaced next call
        price = runner_handler.back_order.order_type.price
        price_move = price < top_value or (price > top_value and periodic_update)
        if price_move or self.pending_cancel_back:
            self.pending_cancel_back = self._cancel(runner_handler, 'back_order', market, 'BACK', price, top_value)

        # cancel lay order if price moved
        price = runner_handler.lay_order.order_type.price
        price_move = price > bottom_value or (price < bottom_value and periodic_update)
        if (price_move or self.pending_cancel_lay) and self.enable_lay:
            self.pending_cancel_lay = self._cancel(runner_handler, 'lay_order', market, 'LAY', price, bottom_value)

        # update previous state boundary max/mins
        runner_handler.prev_boundary_bottom_tick = boundary_bottom_tick
        runner_handler.prev_boundary_top_tick = boundary_top_tick


@register_formatter(SpikeMessageTypes.SPIKE_MSG_PERIODIC)
def formatter(attrs: Dict) -> str:
    return f'periodic update after "{attrs.get("periodic_s")}"s'


@register_formatter(SpikeMessageTypes.SPIKE_MSG_START)
def formatter(attrs: Dict) -> str:
    return '\n'.join([
        f'criteria met:',
        f'-> best back: {attrs.get("best_back", 0):.2f}, best lay: {attrs.get("best_lay", 0):.2f}',
        f'-> ladder spread: {attrs.get("ladder_spread", 0)} within max: {attrs.get("ladder_spread_max", 0)}',
        f'-> ltp min: {attrs.get("ltp_min", 0):.2f}, ltp max: {attrs.get("ltp_max", 0):.2f}',
        f'-> window spread: {attrs.get("window_spread", 0)} meets minimum: {attrs.get("window_spread_min", 0)}'
    ])


@register_formatter(SpikeMessageTypes.SPIKE_MSG_CREATE)
def formatter(attrs: Dict) -> str:
    return f'placing opening "{attrs.get("side")}" order "{attrs.get("order_id")}" ' \
           f'at {attrs.get("price", 0):.2f} for ' \
           f'£{attrs.get("size", 0):.2f}'


@register_formatter(SpikeMessageTypes.SPIKE_MSG_VAL_FAIL)
def formatter(attrs: Dict) -> str:
    return '\n'.join([
        f'variable in attributes not non-zero:',
        f'-> best back: {attrs.get("best_back")}',
        f'-> best lay: {attrs.get("best_lay")}',
        f'-> ltp: {attrs.get("ltp")}',
        f'-> ltp min: {attrs.get("ltp_min")}',
        f'-> ltp max: {attrs.get("ltp_max")}'
    ])


@register_formatter(SpikeMessageTypes.SPIKE_MSG_PRICE_REPLACE)
def formatter(attrs: Dict) -> str:
    return f'replacing order "{attrs.get("order_id")}" on "{attrs.get("side")}" side from {attrs.get("old_price", 0):.2f} to new price '\
           f'{attrs.get("new_price", 0):.2f}'


@register_formatter(SpikeMessageTypes.SPIKE_MSG_BREACHED)
def formatter(attrs: Dict) -> str:
    return f'spike detected on "{attrs.get("side")}" from boundary {attrs.get("old_price", 0):.2f} to ltp ' \
           f'{attrs.get("ltp", 0):.2f} by {attrs.get("spike_ticks")} ticks'


@register_formatter(SpikeMessageTypes.SPIKE_MSG_SPREAD_FAIL)
def formatter(attrs: Dict) -> str:
    return f'failed to validate ladder spread or window spread' \
           f'ladder spread: {attrs.get("ladder_spread")} must be <= max: {attrs.get("ladder_spread_max")}\n' \
           f'window spread: {attrs.get("window_spread")} must be >= min: {attrs.get("window_spread_min")}'


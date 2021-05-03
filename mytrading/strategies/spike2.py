"""
Trade based on back/lay/ltp trend using regression
"""
import logging
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from flumine.order.order import BetfairOrder
from betfairlightweight.resources.bettingresources import MarketBook, RunnerBook
from dataclasses import dataclass
from betfairlightweight.resources import MarketBook
from flumine.markets.market import Market
from flumine.order.order import OrderStatus
from flumine.order.ordertype import LimitOrder, OrderTypes
from functools import partial

from ..process import closest_tick, tick_spread, LTICKS_DECODED
from ..strategy.messages import register_formatter
from ..strategy.runnerhandler import RunnerHandler
from ..strategy import tradestates as basestates
from ..strategy.trademachine import RunnerTradeMachine
from ..strategy.strategy import MyFeatureStrategy
from ..strategy.feature import FeatureHolder
from ..strategy.tradetracker import TradeTracker
from ..process import get_ltps

MIN_BET_AMOUNT = 2
active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class SpikeStateTypes(Enum):
    SPIKE_STATE_MONITOR = 'monitor window orders'
    SPIKE_STATE_BOUNCE = 'wait for bounce back'
    SPIKE_STATE_HEDGE = 'hedging'
    SPIKE_STATE_HEDGE_WAIT = 'waiting for hedge to complete'


@dataclass
class SpikeData:
    best_back: float
    best_lay: float
    ltp: float
    ltp_min: float
    ltp_max: float

    def get_window_price(self, side):
        """
        get hedging price for opening trade whose side specified by `side` parameter
        If open trade side is 'BACK', get rounded down ltp window minimum value
        If open trade side is 'LAY', get rounded up ltp window maximum value
        """
        # validate spike data
        if not self.validate_spike_data():
            return 0

        if side == 'BACK':
            price = self.ltp_min
            return closest_tick(price, return_index=False, round_down=True)
        else:
            price = self.ltp_max
            return closest_tick(price, return_index=False, round_up=True)

    def get_window_price_mk2(self, side):
        """
        get hedging price for opening trade whose side specified by `side` parameter
        If open trade side is 'BACK', get maximum of (rounded down ltp window minimum value) and (best lay - offset tick)
        If open trade side is 'LAY', get minimum of (rounded up ltp window maximum value) and (best back + offset tick)
        """
        # validate spike data
        if not self.validate_spike_data():
            return 0

        if side == 'BACK':
            price = self.ltp_min
            ltp_min_rounded = closest_tick(price, return_index=False, round_down=True)
            lay_tick = closest_tick(self.best_lay, return_index=True)
            lay_tick = max(lay_tick - 1, 0)
            lay_val = LTICKS_DECODED[lay_tick]
            return max(ltp_min_rounded, lay_val)

        else:
            price = self.ltp_max
            ltp_max_rounded = closest_tick(price, return_index=False, round_up=True)
            back_tick = closest_tick(self.best_back, return_index=True)
            back_tick = min(back_tick + 1, len(LTICKS_DECODED) - 1)
            back_val = LTICKS_DECODED[back_tick]
            return min(ltp_max_rounded, back_val)

    def bound_top(self):
        return max(self.ltp, self.ltp_max, self.best_back, self.best_lay)

    def bound_bottom(self):
        return min(self.ltp, self.ltp_min, self.best_back, self.best_lay)

    def validate_spike_data(self):
        return(
                self.best_back and
                self.best_lay and
                self.ltp and
                self.ltp_min and
                self.ltp_max
        )


class SpikeMessageTypes(Enum):
    SPIKE_MSG_START = 'achieved spike criteria'
    SPIKE_MSG_VAL_FAIL = 'failed to validate spike data'
    SPIKE_MSG_CREATE = 'place opening window trades'
    SPIKE_MSG_PRICE_REPLACE = 'replacing price'
    SPIKE_MSG_BREACHED = 'spike reached'
    SPIKE_MSG_SPREAD_FAIL = 'spread validation fail'


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

        # ltp at point of spike
        self.spike_ltp: float = 0

        # track previous state minimum/max odds of which offset applied to place spike orders
        self.previous_max_index: int = 0
        self.previous_min_index: int = 0

        self.first_runner: bool = False
        self.spike_data = SpikeData(best_back=0, best_lay=0, ltp=0, ltp_min=0, ltp_max=0)
        

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
        self.features_config: dict = get_spike_feature_configs(**features_kwargs)

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
                            basestates.TradeStateTypes.PENDING,
                            basestates.TradeStateTypes.WAIT,
                            basestates.TradeStateTypes.HEDGE_SELECT,
                        ]
                    ),
                    basestates.TradeStateWait(
                        wait_ms=self.spike_wait_ms,
                    ),
                    # SpikeTradeStateBounce(
                    #     name=SpikeStateTypes.SPIKE_STATE_BOUNCE,
                    #     wait_ms=self.spike_wait_ms,
                    # ),
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
                    # SpikeTradeStateHedge(
                    #     name=SpikeStateTypes.SPIKE_STATE_HEDGE,
                    #     next_state=SpikeStateTypes.SPIKE_STATE_HEDGE_WAIT,
                    #     min_hedge_price=self.min_hedge_price,
                    # ),
                    # SpikeTradeStateHedgeWait(
                    #     name=SpikeStateTypes.SPIKE_STATE_HEDGE_WAIT,
                    #     next_state=basestates.TradeStateTypes.CLEANING,
                    # ),
                    basestates.TradeStateBin(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStatePending(
                        all_trade_orders=True,
                    ),
                    basestates.TradeStateClean(),
                    # basestates.TradeStateWait(
                    #     wait_ms=self.spike_wait_ms
                    # ),
                ]
            },
            initial_state=basestates.TradeStateCreateTrade.name,
            selection_id=rbk.selection_id,
        )

    def _trade_machine_run(self, mkt: Market, mbk: MarketBook, rbk: RunnerBook, runner_index: int):
        rh = self.market_handlers[mkt.market_id].runner_handlers[rbk.selection_id]
        # get ID for shortest runner from LTPs
        ltps = get_ltps(mbk)
        rh.first_runner = next(iter(ltps.keys()), 0)
        rh.trade_machine.run(mkt, runner_index, rh)


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

        if not spike_data.validate_spike_data():
            return False

        if not (spike_data.best_lay <= self.max_odds and spike_data.best_back <= self.max_odds):
            return False

        window_spread = tick_spread(spike_data.ltp_min, spike_data.ltp_max, check_values=False)
        ladder_spread = tick_spread(spike_data.best_back, spike_data.best_lay, check_values=False)

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

    def enter(self, market: Market, runner_index: int, runner_handler: SpikeRunnerHandler):
        market_book = market.market_book
        runner_handler.back_order = None
        runner_handler.lay_order = None
        self.update_timestamp = market_book.publish_time

    def _place_window_order(self, side: str, runner_handler: SpikeRunnerHandler, price: float, market: Market):
        trade_tracker = runner_handler.trade_tracker
        market_book = market.market_book

        order = trade_tracker.active_trade.create_order(
            side=side,
            order_type=LimitOrder(
                price=price,
                size=self.stake_size
            )
        )
        if side == 'BACK':
            runner_handler.back_order = order
        else:
            runner_handler.lay_order = order
        trade_tracker.log_update(
            msg_type=SpikeMessageTypes.SPIKE_MSG_CREATE,
            dt=market_book.publish_time,
            msg_attrs={
                'side': side,
                'price': price,
                'size': self.stake_size,
            },
            display_odds=price
        )
        market.place_order(runner_handler.back_order)

    def _process_replace(
            self,
            runner_handler: SpikeRunnerHandler,
            side: str,
            boundary_tick,
            window_tick,
            window_val,
            period_update: bool,
            market: Market
    ):
        trade_tracker = runner_handler.trade_tracker
        market_book = market.market_book

        # check back price moved
        if side == 'BACK':
            price = runner_handler.back_order.order_type.price
        else:
            price = runner_handler.lay_order.order_type.price
        proceed = False

        # check if upper boundary is within limit to update
        price_tick = closest_tick(price, return_index=True)
        if abs(boundary_tick - price_tick) <= self.tick_trigger:
            proceed = True
        elif price_tick != window_tick and period_update:
            proceed = True

        # proceed with order replacement if timer exceeded or price drifted
        if proceed:
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_PRICE_REPLACE,
                dt=market_book.publish_time,
                msg_attrs={
                    'side': side,
                    'old_price': price,
                    'new_price': window_val
                },
                display_odds=window_val,
            )

            # cancel order
            if side == 'BACK':
                market.cancel_order(runner_handler.back_order)
                runner_handler.back_order = None
            else:
                market.cancel_order(runner_handler.lay_order)
                runner_handler.lay_order = None

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
            old_tick = runner_handler.previous_max_index
            breach = True

        elif any([
            o.size_matched > 0 for o in trade_tracker.active_trade.orders
            if o.order_type.ORDER_TYPE == OrderTypes.LIMIT and o.side == 'LAY'
        ]):
            # LAY side matched indicator for hedging state to read
            runner_handler.side_matched = 'LAY'
            # get previous tick from LAY side
            old_tick = runner_handler.previous_min_index
            breach = True

        if breach:
            # cancel remaining from both sides if orders exist
            if runner_handler.back_order and runner_handler.back_order.status == OrderStatus.EXECUTABLE:
                market.cancel_order(runner_handler.back_order)
            if runner_handler.lay_order and runner_handler.lay_order.status == OrderStatus.EXECUTABLE:
                market.cancel_order(market, runner_handler.lay_order)

            # set spike ltp for hedging state to read
            runner_handler.spike_ltp = spike_data.ltp

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
        boundary_top_value = spike_data.bound_top()
        boundary_top_tick = closest_tick(boundary_top_value, return_index=True)
        top_tick = min(len(LTICKS_DECODED) - 1, boundary_top_tick + self.tick_offset)
        top_value = LTICKS_DECODED[top_tick]

        boundary_bottom_value = spike_data.bound_bottom()
        boundary_bottom_tick = closest_tick(boundary_bottom_value, return_index=True)
        bottom_tick = max(0, boundary_bottom_tick - self.tick_offset)
        bottom_value = LTICKS_DECODED[bottom_tick]

        # check if breached window
        if self._process_breach(runner_handler, market):
            return self.next_state

        window_spread = tick_spread(spike_data.ltp_min, spike_data.ltp_max, check_values=False)
        ladder_spread = tick_spread(spike_data.best_back, spike_data.best_lay, check_values=False)

        # check back/lay spread is still within tolerance and ltp min/max spread is above tolerance
        if not(ladder_spread <= self.ladder_spread_max and window_spread >= self.window_spread_min):
            trade_tracker.log_update(
                msg_type=SpikeMessageTypes.SPIKE_MSG_SPREAD_FAIL,
                dt=market_book.publish_time,
                msg_attrs={
                    'ladder_spread': ladder_spread,
                    'ladder_spread_max': self.ladder_spread_max,
                    'window_spread': window_spread,
                    'window_spread_min': self.window_spread_min,
                }
            )
            return [
                basestates.TradeStateTypes.BIN,
                basestates.TradeStateTypes.IDLE,
            ]

        # create back order if doesn't exist
        if runner_handler.back_order is None:
            self._place_window_order('BACK', runner_handler, top_value, market)

        # create lay order if doesn't exist
        if runner_handler.lay_order is None and self.enable_lay:
            self._place_window_order('LAY', runner_handler, bottom_value, market)

        # check if need periodic update
        periodic_update = False
        if (market_book.publish_time - self.update_timestamp).total_seconds() >= self.update_s:
            self.update_timestamp = market_book.publish_time
            periodic_update = True

        # cancel back order if price moved so can be replaced next call
        pr = partial(
            self._process_replace, runner_handler=runner_handler, period_update=periodic_update, market=market
        )
        if runner_handler.back_order is not None and runner_handler.back_order.status == OrderStatus.EXECUTABLE:
            pr(side='BACK', boundary_tick=boundary_top_tick, window_tick=top_tick, window_val=top_value)

        # cancel lay order if price moved so can be replaced next cal
        if runner_handler.lay_order is not None and runner_handler.lay_order.status == OrderStatus.EXECUTABLE:
            pr(side='LAY', boundary_tick=boundary_bottom_tick, window_tick=bottom_tick, window_val=bottom_value)

        # update previous state boundary max/mins
        runner_handler.previous_min_index = boundary_bottom_tick
        runner_handler.previous_max_index = boundary_top_tick


class SpikeTradeStateHedge(basestates.TradeStateHedgePlaceBase):
    def get_hedge_price(
            self, market: Market, runner_index: int, runner_handler: SpikeRunnerHandler, outstanding_profit: float
    ) -> float:
        spike_data = runner_handler.spike_data
        return spike_data.get_window_price_mk2('BACK' if runner_handler.side_matched == 'LAY' else 'LAY')


class SpikeTradeStateHedgeWait(basestates.TradeStateHedgeWaitBase):
    def price_moved(self, market: Market, runner_index: int, runner_handler: SpikeRunnerHandler) -> float:
        spike_data = runner_handler.spike_data
        return spike_data.get_window_price_mk2('BACK' if runner_handler.side_matched == 'LAY' else 'LAY')


class SpikeTradeStateBounce(basestates.TradeStateWait):
    def run(self, market: Market, runner_index: int, runner_handler: SpikeRunnerHandler):
        market_book = market.market_book
        spike_data = runner_handler.spike_data
        if (market_book.publish_time - self.start_time) >= self.td:
            return True
        elif not spike_data.validate_spike_data():
            return True
        elif runner_handler.side_matched == 'LAY' and spike_data.best_back > runner_handler.spike_ltp:
            return True
        elif runner_handler.side_matched == 'BACK' and spike_data.best_lay < runner_handler.spike_ltp:
            return True


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
    return f'placing opening "{attrs.get("side")}" order at {attrs.get("price", 0):.2f} for ' \
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
    return f'replacing order on "{attrs.get("side")}" side from {attrs.get("old_price", 0):.2f} to new price '\
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


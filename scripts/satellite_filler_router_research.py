"""Step-5B research: short-horizon Satellite filler router.

The protected product runner is intentionally untouched. This research-only simulator
keeps the ten Core profiles canonical, uses the five frozen Step-4 Satellite profiles,
lets Satellites consume only genuinely free slots (max one slot per Satellite), and
allows a materially stronger Core entry to reclaim a Satellite slot at the next
executable open.

Router parameters are calibrated on the pre-holdout training window only. The final
real-USDC Satellite year is rejection-only and may never retune the router or subset.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.engine import candle_snapshot_sha256
from hixton.backtest.metrics import calculate_metrics
from hixton.backtest.models import (
    BASELINE_COSTS,
    ONE,
    STRESS_COSTS,
    ZERO,
    CostModel,
    EquityPoint,
    ExecutionRules,
    Fill,
    PortfolioBacktestResult,
    Trade,
)
from hixton.constants import TIMEFRAME_DELTA
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.allocation import RANKED_REPEAT, allocate_entry_slots
from hixton.domain.capital import capital_plan
from hixton.domain.models import (
    Candle,
    IndicatorPoint,
    Signal,
    SignalAction,
    StrategyParameters,
    StrategySemantics,
)
from hixton.domain.risk import PortfolioRiskState, evaluate_portfolio_risk
from hixton.domain.strategy import HixtonStrategy, entry_priority
from hixton.domain.trade_policy import TradePolicy, TradePolicyGate
from hixton.domain.versions import V6_COIN_STRATEGY
from scripts.satellite_shared_portfolio_research import (
    DEFAULT_CHECKPOINT,
    _comparison,
    _load,
    _load_histories,
    _profiles,
    _rules,
    _satellite_profiles,
)

D = Decimal
HUNDRED = D("100")
VERSION = "HIXTON-V6-SATELLITE-STEP5B-FILLER-ROUTER"
HORIZON_GRID_HOURS = (12, 24, 48)
HYSTERESIS_GRID_ATR = (D("0"), D("0.20"))


@dataclass(slots=True)
class OpenTrade:
    signal: Signal
    fill: Fill
    quantity: Decimal
    cost_basis: Decimal
    slots: int
    highest_close: float
    is_satellite: bool


@dataclass(frozen=True, slots=True)
class RouterConfig:
    filler_horizon_hours: int
    hysteresis_atr: Decimal

    @property
    def key(self) -> str:
        return f"h{self.filler_horizon_hours}_m{self.hysteresis_atr}"


def _d(value: float | Decimal | int | str) -> Decimal:
    return D(str(value))


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= ZERO:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _equal_weight_buy_and_hold(
    candles_by_symbol: dict[str, list[Candle]],
    starting_cash: Decimal,
    costs: CostModel,
) -> Decimal:
    allocation = starting_cash / D(len(candles_by_symbol))
    ending = ZERO
    for candles in candles_by_symbol.values():
        entry = _d(candles[0].open) * (ONE + costs.adverse_price_rate)
        net_quantity = allocation / entry * (ONE - costs.fee_rate)
        ending += net_quantity * _d(candles[-1].close)
    return ending


def _switch_cost_score(
    *,
    costs: CostModel,
    satellite_point: IndicatorPoint,
    core_signal: Signal,
) -> Decimal:
    """Normalize one exit side + one entry side into ATR-like score units."""

    side_rate = costs.fee_rate + costs.adverse_price_rate
    sat_atr = _d(satellite_point.atr or 0)
    core_atr = _d(core_signal.atr or 0)
    sat_close = _d(satellite_point.candle.close)
    core_close = _d(core_signal.close)
    if sat_atr <= 0 or core_atr <= 0 or sat_close <= 0 or core_close <= 0:
        return D("999")
    sat_units = side_rate * sat_close / sat_atr
    core_units = side_rate * core_close / core_atr
    return sat_units + core_units


def _remaining_satellite_score(
    *,
    trade: OpenTrade,
    point: IndicatorPoint | None,
    at: datetime,
    config: RouterConfig,
) -> Decimal:
    """Point-in-time filler value: entry strength decays with occupancy; live trend can extend it."""

    entry_strength = max(D("0"), _d(trade.signal.breakout_strength or 0))
    age_hours = max(
        D("0"),
        D(str((at - trade.fill.fill_time_utc).total_seconds() / 3600)),
    )
    horizon = D(config.filler_horizon_hours)
    age_factor = max(D("0"), ONE - age_hours / horizon)
    score = entry_strength * age_factor
    if point is not None and point.atr and point.vidya is not None and point.atr > 0:
        trend_health = max(
            D("0"),
            _d(point.candle.close - point.vidya) / _d(point.atr),
        )
        # A good current trend can extend a filler, but never turn it into a long-hold
        # primary position. Cap the live contribution deliberately.
        score += min(D("0.50"), trend_health * D("0.25"))
    return score


def _candidate_core_score(signal: Signal) -> Decimal:
    return max(D("0"), _d(signal.breakout_strength or 0))


def run_filler_router_portfolio(
    *,
    candles_by_symbol: dict[str, list[Candle]],
    report_start_utc: datetime,
    report_end_utc: datetime,
    starting_cash: Decimal,
    target_notional: Decimal,
    slot_count: int,
    costs: CostModel,
    execution_rules: dict[str, ExecutionRules],
    strategy_parameters_by_symbol: dict[str, StrategyParameters],
    trade_policies_by_symbol: dict[str, TradePolicy],
    symbols: tuple[str, ...],
    core_symbols: tuple[str, ...],
    satellite_symbols: tuple[str, ...],
    router_config: RouterConfig,
) -> tuple[PortfolioBacktestResult, list[dict[str, object]]]:
    if tuple(candles_by_symbol) != symbols:
        raise ValueError("router input universe/order mismatch")
    if set(strategy_parameters_by_symbol) != set(symbols):
        raise ValueError("router parameters must cover the full research universe")
    if set(trade_policies_by_symbol) != set(symbols):
        raise ValueError("router policies must cover the full research universe")
    if slot_count <= 0 or starting_cash <= 0 or target_notional <= 0:
        raise ValueError("invalid capital plan")

    parameters = V6_COIN_STRATEGY.parameters
    warmup_start = report_start_utc - parameters.warmup_bars * TIMEFRAME_DELTA
    selected_by_symbol: dict[str, list[Candle]] = {}
    report_by_symbol: dict[str, list[Candle]] = {}
    for symbol in symbols:
        selected = [
            candle
            for candle in candles_by_symbol[symbol]
            if warmup_start <= candle.open_time_utc < report_end_utc
        ]
        audit_candles(
            selected,
            expected_symbol=symbol,
            expected_start=warmup_start,
            expected_end_exclusive=report_end_utc,
        ).require_valid()
        selected_by_symbol[symbol] = selected
        report_by_symbol[symbol] = [
            candle for candle in selected if candle.open_time_utc >= report_start_utc
        ]

    rows = tuple(zip(*(selected_by_symbol[symbol] for symbol in symbols), strict=True))
    for row in rows:
        if len({candle.open_time_utc for candle in row}) != 1:
            raise ValueError("router candles are not aligned")

    strategies = {
        symbol: HixtonStrategy(
            symbol,
            parameters=strategy_parameters_by_symbol[symbol],
            semantics=V6_COIN_STRATEGY.semantics,
            strategy_version=VERSION,
        )
        for symbol in symbols
    }
    gates = {
        symbol: TradePolicyGate(trade_policies_by_symbol[symbol]) for symbol in symbols
    }
    core_set = frozenset(core_symbols)
    satellite_set = frozenset(satellite_symbols)

    cash = starting_cash
    positions: dict[str, OpenTrade] = {}
    dust = dict.fromkeys(symbols, ZERO)
    pending: list[Signal] = []
    signals: list[Signal] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    curve: list[EquityPoint] = []
    blocked: list[str] = []
    router_events: list[dict[str, object]] = []
    last_points: dict[str, IndicatorPoint] = {}
    max_concurrent = 0

    risk_state = PortfolioRiskState(
        high_water_equity_usdc=starting_cash,
        day_start_equity_usdc=starting_cash,
        day_start_date_utc=report_start_utc.date().isoformat(),
    )
    risk_halted_at: datetime | None = None
    daily_paused_bars = 0

    def close_position(symbol: str, *, at: datetime, candle: Candle, reason_id: str) -> bool:
        nonlocal cash
        trade = positions.get(symbol)
        if trade is None:
            return False
        rule = execution_rules[symbol]
        reference = _d(candle.open)
        fill_price = reference * (ONE - costs.adverse_price_rate)
        sell_quantity = _round_down(trade.quantity, rule.step_size)
        gross_quote = sell_quantity * fill_price
        if sell_quantity < rule.min_qty or gross_quote < rule.min_notional:
            blocked.append(f"{reason_id}:EXIT_BECAME_DUST")
            dust[symbol] += trade.quantity
            del positions[symbol]
            return False
        residual = trade.quantity - sell_quantity
        fee_quote = gross_quote * costs.fee_rate
        net_quote = gross_quote - fee_quote
        modeled_adverse = sell_quantity * (reference - fill_price)
        basis_fraction = sell_quantity / trade.quantity
        realized_basis = trade.cost_basis * basis_fraction
        realized_pnl = net_quote - realized_basis
        fills.append(
            Fill(
                signal_id=reason_id,
                action=SignalAction.EXIT_LONG,
                fill_time_utc=at,
                reference_open=reference,
                fill_price=fill_price,
                base_quantity=sell_quantity,
                quote_value=gross_quote,
                fee_quote_equivalent=fee_quote,
                modeled_spread_slippage=modeled_adverse,
            )
        )
        cash += net_quote
        dust[symbol] += residual
        trades.append(
            Trade(
                symbol=symbol,
                entry_signal_id=trade.signal.signal_id,
                exit_signal_id=reason_id,
                entry_time_utc=trade.fill.fill_time_utc,
                exit_time_utc=at,
                entry_quote_spend=realized_basis,
                exit_quote_receive=net_quote,
                realized_pnl=realized_pnl,
                realized_return_pct=realized_pnl / realized_basis * HUNDRED,
                entry_price=trade.fill.fill_price,
                exit_price=fill_price,
                sold_base_quantity=sell_quantity,
                residual_dust_quantity=residual,
                holding_hours=D(str((at - trade.fill.fill_time_utc).total_seconds() / 3600)),
                slot_count=trade.slots,
            )
        )
        del positions[symbol]
        return True

    def open_position(signal: Signal, *, slots: int, at: datetime, candle: Candle) -> bool:
        nonlocal cash
        if slots <= 0 or signal.symbol in positions:
            return False
        rule = execution_rules[signal.symbol]
        budget = min(target_notional * D(slots), cash)
        reference = _d(candle.open)
        fill_price = reference * (ONE + costs.adverse_price_rate)
        gross_quantity = _round_down(budget / fill_price, rule.step_size)
        quote_spend = min(gross_quantity * fill_price, budget)
        if gross_quantity < rule.min_qty or quote_spend < rule.min_notional:
            blocked.append(f"{signal.signal_id}:BELOW_EXCHANGE_MINIMUM")
            return False
        if quote_spend <= ZERO or quote_spend > cash:
            blocked.append(f"{signal.signal_id}:INSUFFICIENT_CASH")
            return False
        fee_base = gross_quantity * costs.fee_rate
        net_quantity = gross_quantity - fee_base
        fee_quote = fee_base * fill_price
        modeled_adverse = gross_quantity * (fill_price - reference)
        fill = Fill(
            signal_id=signal.signal_id,
            action=SignalAction.ENTER_LONG,
            fill_time_utc=at,
            reference_open=reference,
            fill_price=fill_price,
            base_quantity=net_quantity,
            quote_value=quote_spend,
            fee_quote_equivalent=fee_quote,
            modeled_spread_slippage=modeled_adverse,
        )
        cash -= quote_spend
        positions[signal.symbol] = OpenTrade(
            signal=signal,
            fill=fill,
            quantity=net_quantity,
            cost_basis=quote_spend,
            slots=slots,
            highest_close=float(fill_price),
            is_satellite=signal.symbol in satellite_set,
        )
        fills.append(fill)
        return True

    for row in rows:
        open_time = row[0].open_time_utc
        in_report = report_start_utc <= open_time < report_end_utc
        candles = {candle.symbol: candle for candle in row}

        if in_report and pending:
            exits = [s for s in pending if s.action is SignalAction.EXIT_LONG]
            entries = [s for s in pending if s.action is SignalAction.ENTER_LONG]

            # Natural/soft filler exits happen before entries at the same executable open.
            for signal in exits:
                if not close_position(
                    signal.symbol,
                    at=open_time,
                    candle=candles[signal.symbol],
                    reason_id=signal.signal_id,
                ):
                    if signal.symbol not in positions:
                        blocked.append(f"{signal.signal_id}:POSITION_ALREADY_CLOSED")

            core_entries = [s for s in entries if s.symbol in core_set]
            satellite_entries = [s for s in entries if s.symbol in satellite_set]
            core_entries.sort(
                key=lambda signal: entry_priority(
                    signal.breakout_strength, signal.symbol, core_symbols
                )
            )
            satellite_entries.sort(
                key=lambda signal: entry_priority(
                    signal.breakout_strength, signal.symbol, satellite_symbols
                )
            )

            # Compute the Core allocation that would exist if filler slots were
            # completely reclaimable. This preserves the protected Core ranked-repeat
            # exposure whenever the Core signal is strong enough to justify the handoff.
            core_used_slots = sum(
                p.slots for p in positions.values() if not p.is_satellite
            )
            ideal_core_alloc = allocate_entry_slots(
                [s.symbol for s in core_entries if s.symbol not in positions],
                free_slots=max(0, slot_count - core_used_slots),
                policy=RANKED_REPEAT,
            )

            for core_signal in core_entries:
                if core_signal.symbol in positions:
                    blocked.append(f"{core_signal.signal_id}:POSITION_ALREADY_OPEN")
                    continue
                desired_slots = ideal_core_alloc.get(core_signal.symbol, 0)
                if desired_slots <= 0:
                    blocked.append(f"{core_signal.signal_id}:NO_FREE_SLOT")
                    continue

                # Reclaim as many one-slot fillers as required to restore the Core
                # allocation, but only when this Core signal clears the value/cost margin.
                while True:
                    used_slots = sum(p.slots for p in positions.values())
                    free_slots = max(0, slot_count - used_slots)
                    if free_slots >= desired_slots:
                        break
                    candidates = [
                        (symbol, trade)
                        for symbol, trade in positions.items()
                        if trade.is_satellite
                    ]
                    if not candidates:
                        break
                    ranked_running: list[
                        tuple[Decimal, str, OpenTrade, Decimal]
                    ] = []
                    for symbol, trade in candidates:
                        point = last_points.get(symbol)
                        remaining = _remaining_satellite_score(
                            trade=trade,
                            point=point,
                            at=open_time,
                            config=router_config,
                        )
                        switch_cost = (
                            _switch_cost_score(
                                costs=costs,
                                satellite_point=point,
                                core_signal=core_signal,
                            )
                            if point is not None
                            else D("999")
                        )
                        ranked_running.append(
                            (remaining, symbol, trade, switch_cost)
                        )
                    ranked_running.sort(key=lambda row: row[0])
                    remaining, sat_symbol, sat_trade, switch_cost = ranked_running[0]
                    core_score = _candidate_core_score(core_signal)
                    threshold = (
                        remaining
                        + switch_cost
                        + router_config.hysteresis_atr
                    )
                    decision = "SWITCH" if core_score > threshold else "HOLD"
                    router_events.append(
                        {
                            "time_utc": open_time.isoformat(),
                            "satellite_symbol": sat_symbol,
                            "core_candidate": core_signal.symbol,
                            "desired_core_slots": desired_slots,
                            "satellite_remaining_score": str(remaining),
                            "core_candidate_score": str(core_score),
                            "normalized_switch_cost_score": str(switch_cost),
                            "hysteresis_atr": str(router_config.hysteresis_atr),
                            "decision": decision,
                            "satellite_age_hours": str(
                                D(
                                    str(
                                        (
                                            open_time
                                            - sat_trade.fill.fill_time_utc
                                        ).total_seconds()
                                        / 3600
                                    )
                                )
                            ),
                        }
                    )
                    if decision != "SWITCH":
                        break
                    close_position(
                        sat_symbol,
                        at=open_time,
                        candle=candles[sat_symbol],
                        reason_id=f"ROUTER_SWITCH::{core_signal.signal_id}",
                    )

                used_slots = sum(p.slots for p in positions.values())
                free_slots = max(0, slot_count - used_slots)
                slots = min(desired_slots, free_slots)
                if slots <= 0:
                    blocked.append(f"{core_signal.signal_id}:NO_FREE_SLOT")
                    continue
                open_position(
                    core_signal,
                    slots=slots,
                    at=open_time,
                    candle=candles[core_signal.symbol],
                )

            # Satellites are fillers only: they never displace Core and never take more
            # than one slot each, even if ranked-repeat would otherwise stack capital.
            for signal in satellite_entries:
                if signal.symbol in positions:
                    blocked.append(f"{signal.signal_id}:POSITION_ALREADY_OPEN")
                    continue
                used_slots = sum(p.slots for p in positions.values())
                if used_slots >= slot_count:
                    blocked.append(f"{signal.signal_id}:NO_FREE_SLOT")
                    continue
                open_position(
                    signal,
                    slots=1,
                    at=open_time,
                    candle=candles[signal.symbol],
                )
            pending = []

        points: dict[str, IndicatorPoint] = {}
        decisions = {}
        for symbol in symbols:
            point = strategies[symbol].update(candles[symbol])
            points[symbol] = point
            last_points[symbol] = point
            position = positions.get(symbol)
            if position is not None:
                position.highest_close = max(position.highest_close, candles[symbol].close)
            decisions[symbol] = gates[symbol].decide(
                point,
                entry_price=float(position.fill.fill_price) if position else None,
                entry_atr=position.signal.atr if position else 0.0,
                highest_close=position.highest_close if position else 0.0,
            )

            # Soft short-horizon filler exit: if the training-calibrated remaining-value
            # score has fully decayed and the canonical strategy has not already exited,
            # schedule an exit for the next open.
            if (
                in_report
                and position is not None
                and position.is_satellite
                and decisions[symbol].signal is None
            ):
                remaining = _remaining_satellite_score(
                    trade=position,
                    point=point,
                    at=point.candle.close_time_utc,
                    config=router_config,
                )
                age_hours = (
                    point.candle.close_time_utc - position.fill.fill_time_utc
                ).total_seconds() / 3600
                if age_hours >= router_config.filler_horizon_hours and remaining <= D("0.50"):
                    forced = HixtonStrategy.signal_for(
                        replace(point, flip_down=True, flip_up=False),
                        is_long=True,
                    )
                    if forced is not None:
                        decisions[symbol] = replace(
                            decisions[symbol],
                            signal=forced,
                            exit_reason="RESEARCH_FILLER_VALUE_DECAY",
                        )

        if in_report:
            max_concurrent = max(
                max_concurrent,
                sum(p.slots for p in positions.values()),
            )
            position_value = sum(
                (
                    ((positions[s].quantity if s in positions else ZERO) + dust[s])
                    * _d(candles[s].close)
                    for s in symbols
                ),
                ZERO,
            )
            equity = cash + position_value
            daily_paused = False
            risk = evaluate_portfolio_risk(
                risk_state,
                equity=equity,
                at=max(c.close_time_utc for c in row),
            )
            if not risk_state.halted and risk.state.halted:
                risk_halted_at = max(c.close_time_utc for c in row)
            risk_state = risk.state
            daily_paused = risk.daily_paused
            daily_paused_bars += int(daily_paused)

            new_pending: list[Signal] = []
            for symbol in symbols:
                signal = decisions[symbol].signal
                if signal is None:
                    continue
                signals.append(signal)
                if decisions[symbol].block_reason:
                    blocked.append(f"{signal.signal_id}:{decisions[symbol].block_reason}")
                    continue
                if signal.action is SignalAction.ENTER_LONG:
                    if risk_state.halted:
                        blocked.append(
                            f"{signal.signal_id}:{risk_state.halt_reason or 'HALTED'}"
                        )
                        continue
                    if daily_paused:
                        blocked.append(f"{signal.signal_id}:DAILY_LOSS_5_PERCENT")
                        continue
                new_pending.append(signal)
            pending = new_pending
            curve.append(
                EquityPoint(
                    time_utc=max(c.close_time_utc for c in row),
                    cash=cash,
                    position_value=position_value,
                    equity=equity,
                    active_position=bool(positions),
                )
            )

    if not curve:
        raise ValueError("router report window is empty")

    metrics = calculate_metrics(
        starting_equity=starting_cash,
        ending_equity=curve[-1].equity,
        report_start_utc=report_start_utc,
        report_end_utc=report_end_utc,
        trades=tuple(trades),
        fills=tuple(fills),
        equity_curve=tuple(curve),
        buy_and_hold_ending_equity=_equal_weight_buy_and_hold(
            report_by_symbol, starting_cash, costs
        ),
    )
    result = PortfolioBacktestResult(
        symbols=symbols,
        report_start_utc=report_start_utc,
        report_end_utc=report_end_utc,
        warmup_start_utc=warmup_start,
        cost_model=costs,
        starting_cash=starting_cash,
        target_notional=target_notional,
        slot_count=slot_count,
        slot_allocation="core_ranked_repeat_satellite_one_slot_filler",
        signals=tuple(signals),
        fills=tuple(fills),
        trades=tuple(trades),
        equity_curve=tuple(curve),
        blocked_signals=tuple(blocked),
        pending_signals_at_end=tuple(pending),
        open_symbols_at_end=tuple(s for s in symbols if s in positions),
        dust_quantity_by_symbol=dust,
        max_concurrent_positions=max_concurrent,
        risk_limits_applied=True,
        risk_halted_at_utc=risk_halted_at,
        daily_paused_bars=daily_paused_bars,
        metrics=metrics,
        data_snapshot_sha256_by_symbol={
            symbol: candle_snapshot_sha256(selected_by_symbol[symbol])
            for symbol in symbols
        },
    )
    return result, router_events


def _summary(
    result: PortfolioBacktestResult,
    router_events: list[dict[str, object]],
    *,
    core_symbols: tuple[str, ...],
    satellite_symbols: tuple[str, ...],
) -> dict[str, object]:
    points = result.equity_curve
    signal_symbol = {signal.signal_id: signal.symbol for signal in result.signals}
    blocked_core = 0
    blocked_sat = 0
    for item in result.blocked_signals:
        signal_id, reason = item.rsplit(":", 1)
        if reason != "NO_FREE_SLOT":
            continue
        symbol = signal_symbol.get(signal_id)
        if symbol in core_symbols:
            blocked_core += 1
        elif symbol in satellite_symbols:
            blocked_sat += 1

    sat_trades = [t for t in result.trades if t.symbol in satellite_symbols]
    sat_pnl = sum((t.realized_pnl for t in sat_trades), ZERO)
    sat_hours = sum((t.holding_hours for t in sat_trades), ZERO)
    average_hold = (
        sat_hours / D(len(sat_trades)) if sat_trades else None
    )
    max_hold = max((t.holding_hours for t in sat_trades), default=None)
    zero_hours = sum(not p.active_position for p in points)
    avg_deployed = (
        sum((p.position_value for p in points), ZERO) / D(len(points))
        if points else ZERO
    )
    switch_events = [e for e in router_events if e["decision"] == "SWITCH"]
    hold_events = [e for e in router_events if e["decision"] == "HOLD"]
    per_sat = {
        symbol: {
            "completed_cycles": sum(t.symbol == symbol for t in sat_trades),
            "realized_pnl": str(
                sum((t.realized_pnl for t in sat_trades if t.symbol == symbol), ZERO)
            ),
            "position_hours": str(
                sum((t.holding_hours for t in sat_trades if t.symbol == symbol), ZERO)
            ),
        }
        for symbol in satellite_symbols
    }
    return {
        "ending_equity": str(result.metrics.ending_equity),
        "net_pnl": str(result.metrics.net_pnl),
        "return_pct": str(result.metrics.return_pct),
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "completed_position_cycles": result.metrics.completed_trades,
        "satellite_completed_cycles": len(sat_trades),
        "satellite_realized_pnl": str(sat_pnl),
        "satellite_position_hours": str(sat_hours),
        "satellite_average_holding_hours": None if average_hold is None else str(average_hold),
        "satellite_max_holding_hours": None if max_hold is None else str(max_hold),
        "profit_per_satellite_position_hour": (
            None if sat_hours <= 0 else str(sat_pnl / sat_hours)
        ),
        "zero_position_hours": zero_hours,
        "average_position_value_usdc": str(avg_deployed),
        "blocked_core_no_free_slot": blocked_core,
        "blocked_satellite_no_free_slot": blocked_sat,
        "router_switch_count": len(switch_events),
        "router_hold_count": len(hold_events),
        "total_fees": str(result.metrics.total_fees),
        "modeled_spread_slippage": str(result.metrics.modeled_spread_slippage),
        "per_satellite": per_sat,
    }


def _cmp(candidate: dict[str, object], reference: dict[str, object]) -> dict[str, object]:
    return {
        "ending_equity_delta": str(
            _d(candidate["ending_equity"]) - _d(reference["ending_equity"])
        ),
        "zero_position_hours_reduced": int(reference["zero_position_hours"])
        - int(candidate["zero_position_hours"]),
        "average_deployed_delta_usdc": str(
            _d(candidate["average_position_value_usdc"])
            - _d(reference["average_position_value_usdc"])
        ),
        "blocked_core_delta": int(candidate["blocked_core_no_free_slot"])
        - int(reference["blocked_core_no_free_slot"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/satellite-filler-router-research.json"),
    )
    parser.add_argument("--capital", default="250")
    args = parser.parse_args()

    checkpoint = _load(args.checkpoint)
    capital = D(str(args.capital))
    sat_symbols, sat_parameters, sat_policies, sat_sources = _satellite_profiles(
        checkpoint
    )
    core_symbols = V6_COIN_STRATEGY.symbols
    all_symbols = core_symbols + sat_symbols
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client, all_symbols)
    (
        report_start,
        validation_start,
        report_end,
        proxy_candles,
        validation_candles,
        provenance,
    ) = _load_histories(
        client=client,
        satellite_symbols=sat_symbols,
        satellite_sources=sat_sources,
        execution_rules=rules,
    )
    parameters, policies = _profiles(sat_parameters, sat_policies)
    plan = capital_plan(capital)

    def run(
        *,
        window: str,
        satellites: tuple[str, ...],
        costs: CostModel,
        config: RouterConfig,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        if window == "training":
            candles = proxy_candles
            start, end = report_start, validation_start
        elif window == "holdout":
            candles = validation_candles
            start, end = validation_start, report_end
        elif window == "full":
            candles = proxy_candles
            start, end = report_start, report_end
        else:
            raise ValueError(window)
        symbols = core_symbols + satellites
        result, events = run_filler_router_portfolio(
            candles_by_symbol={s: candles[s] for s in symbols},
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=capital,
            target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,
            costs=costs,
            execution_rules={s: rules[s] for s in symbols},
            strategy_parameters_by_symbol={s: parameters[s] for s in symbols},
            trade_policies_by_symbol={s: policies[s] for s in symbols},
            symbols=symbols,
            core_symbols=core_symbols,
            satellite_symbols=satellites,
            router_config=config,
        )
        return _summary(
            result,
            events,
            core_symbols=core_symbols,
            satellite_symbols=satellites,
        ), events

    # Core-only reference is evaluated through the same research engine, so only
    # Satellite/router behavior differs.
    neutral = RouterConfig(24, D("0.20"))
    core_base, _ = run(
        window="training", satellites=(), costs=BASELINE_COSTS, config=neutral
    )
    core_stress, _ = run(
        window="training", satellites=(), costs=STRESS_COSTS, config=neutral
    )

    configs: list[dict[str, object]] = []
    for hours in HORIZON_GRID_HOURS:
        for margin in HYSTERESIS_GRID_ATR:
            config = RouterConfig(hours, margin)
            base, _ = run(
                window="training",
                satellites=sat_symbols,
                costs=BASELINE_COSTS,
                config=config,
            )
            stress, _ = run(
                window="training",
                satellites=sat_symbols,
                costs=STRESS_COSTS,
                config=config,
            )
            base_cmp = _cmp(base, core_base)
            stress_cmp = _cmp(stress, core_stress)
            min_delta = min(
                _d(base_cmp["ending_equity_delta"]),
                _d(stress_cmp["ending_equity_delta"]),
            )
            configs.append(
                {
                    "config": {
                        "filler_horizon_hours": hours,
                        "hysteresis_atr": str(margin),
                    },
                    "baseline": base,
                    "stress": stress,
                    "baseline_vs_core": base_cmp,
                    "stress_vs_core": stress_cmp,
                    "min_ending_equity_delta": str(min_delta),
                    "min_satellite_realized_pnl": str(
                        min(
                            _d(base["satellite_realized_pnl"]),
                            _d(stress["satellite_realized_pnl"]),
                        )
                    ),
                }
            )
    configs.sort(
        key=lambda row: (
            _d(row["min_ending_equity_delta"]),
            _d(row["min_satellite_realized_pnl"]),
            -_d(row["baseline"]["satellite_average_holding_hours"] or "999999"),
        ),
        reverse=True,
    )
    winner = configs[0]
    frozen = RouterConfig(
        int(winner["config"]["filler_horizon_hours"]),
        _d(winner["config"]["hysteresis_atr"]),
    )

    # With router frozen, select a complementary Satellite subset on training only.
    selected: list[str] = []
    remaining = list(sat_symbols)
    rounds: list[dict[str, object]] = []
    while remaining:
        current = tuple(selected)
        current_base, _ = run(
            window="training", satellites=current, costs=BASELINE_COSTS, config=frozen
        )
        current_stress, _ = run(
            window="training", satellites=current, costs=STRESS_COSTS, config=frozen
        )
        rows: list[dict[str, object]] = []
        for symbol in remaining:
            trial = tuple(selected + [symbol])
            base, _ = run(
                window="training", satellites=trial, costs=BASELINE_COSTS, config=frozen
            )
            stress, _ = run(
                window="training", satellites=trial, costs=STRESS_COSTS, config=frozen
            )
            base_cmp = _cmp(base, current_base)
            stress_cmp = _cmp(stress, current_stress)
            added_base = _d(base["per_satellite"][symbol]["realized_pnl"])
            added_stress = _d(stress["per_satellite"][symbol]["realized_pnl"])
            min_delta = min(
                _d(base_cmp["ending_equity_delta"]),
                _d(stress_cmp["ending_equity_delta"]),
            )
            productive = (
                int(base_cmp["zero_position_hours_reduced"]) > 0
                or int(stress_cmp["zero_position_hours_reduced"]) > 0
                or _d(base_cmp["average_deployed_delta_usdc"]) > 0
                or _d(stress_cmp["average_deployed_delta_usdc"]) > 0
            )
            advance = (
                min_delta > 0
                and added_base > 0
                and added_stress > 0
                and productive
                and int(base_cmp["blocked_core_delta"]) <= 0
                and int(stress_cmp["blocked_core_delta"]) <= 0
            )
            rows.append(
                {
                    "symbol": symbol,
                    "trial_satellites": list(trial),
                    "baseline_vs_current": base_cmp,
                    "stress_vs_current": stress_cmp,
                    "added_realized_pnl_baseline": str(added_base),
                    "added_realized_pnl_stress": str(added_stress),
                    "min_ending_equity_delta": str(min_delta),
                    "advance": advance,
                }
            )
        rows.sort(
            key=lambda row: (
                _d(row["min_ending_equity_delta"]),
                min(
                    _d(row["added_realized_pnl_baseline"]),
                    _d(row["added_realized_pnl_stress"]),
                ),
            ),
            reverse=True,
        )
        best = rows[0]
        rounds.append(
            {
                "round": len(rounds) + 1,
                "selected_before": list(selected),
                "candidates": rows,
                "winner": best["symbol"] if best["advance"] else None,
            }
        )
        if best["advance"] is not True:
            break
        selected.append(str(best["symbol"]))
        remaining.remove(str(best["symbol"]))

    frozen_subset = tuple(selected)

    # Rejection-only real-USDC holdout.
    holdout_core_base, _ = run(
        window="holdout", satellites=(), costs=BASELINE_COSTS, config=frozen
    )
    holdout_core_stress, _ = run(
        window="holdout", satellites=(), costs=STRESS_COSTS, config=frozen
    )
    holdout_base, holdout_events_base = run(
        window="holdout",
        satellites=frozen_subset,
        costs=BASELINE_COSTS,
        config=frozen,
    )
    holdout_stress, holdout_events_stress = run(
        window="holdout",
        satellites=frozen_subset,
        costs=STRESS_COSTS,
        config=frozen,
    )
    hb = _cmp(holdout_base, holdout_core_base)
    hs = _cmp(holdout_stress, holdout_core_stress)

    all_holdout_positive = bool(frozen_subset) and all(
        _d(holdout_base["per_satellite"][s]["realized_pnl"]) > 0
        and _d(holdout_stress["per_satellite"][s]["realized_pnl"]) > 0
        and int(holdout_base["per_satellite"][s]["completed_cycles"]) > 0
        and int(holdout_stress["per_satellite"][s]["completed_cycles"]) > 0
        for s in frozen_subset
    )
    holdout_productive = (
        int(hb["zero_position_hours_reduced"]) > 0
        or int(hs["zero_position_hours_reduced"]) > 0
        or _d(hb["average_deployed_delta_usdc"]) > 0
        or _d(hs["average_deployed_delta_usdc"]) > 0
    )
    holdout_pass = (
        bool(frozen_subset)
        and _d(hb["ending_equity_delta"]) > 0
        and _d(hs["ending_equity_delta"]) > 0
        and int(hb["blocked_core_delta"]) <= 0
        and int(hs["blocked_core_delta"]) <= 0
        and holdout_productive
        and all_holdout_positive
    )

    # Full 3y descriptive/rejection-only.
    full_core_base, _ = run(
        window="full", satellites=(), costs=BASELINE_COSTS, config=frozen
    )
    full_core_stress, _ = run(
        window="full", satellites=(), costs=STRESS_COSTS, config=frozen
    )
    full_base, _ = run(
        window="full", satellites=frozen_subset, costs=BASELINE_COSTS, config=frozen
    )
    full_stress, _ = run(
        window="full", satellites=frozen_subset, costs=STRESS_COSTS, config=frozen
    )
    fb = _cmp(full_base, full_core_base)
    fs = _cmp(full_stress, full_core_stress)
    full_pass = (
        _d(fb["ending_equity_delta"]) > 0
        and _d(fs["ending_equity_delta"]) > 0
        and int(fb["blocked_core_delta"]) <= 0
        and int(fs["blocked_core_delta"]) <= 0
    )

    step5b_pass = holdout_pass and full_pass
    output = {
        "schema_version": 1,
        "study": "SATELLITE_STEP5B_SHORT_HORIZON_FILLER_ROUTER",
        "research_only": True,
        "activation_performed": False,
        "capital_usdc_shared_account": str(capital),
        "step4_checkpoint_run_id": checkpoint.get("source_run_id"),
        "step4_advancing_symbols": list(sat_symbols),
        "owner_intent": (
            "Satellites are short-horizon idle-capital fillers. They use free capacity, "
            "never displace an open Core position, and may be exited when a materially "
            "stronger Core entry clears point-in-time remaining-value + cost margin."
        ),
        "training_only_router_grid": configs,
        "frozen_router": {
            "filler_horizon_hours": frozen.filler_horizon_hours,
            "hysteresis_atr": str(frozen.hysteresis_atr),
        },
        "training_subset_selection": {
            "rounds": rounds,
            "frozen_selected_satellites": list(frozen_subset),
            "not_selected": [s for s in sat_symbols if s not in frozen_subset],
        },
        "real_usdc_holdout": {
            "baseline_vs_core": hb,
            "stress_vs_core": hs,
            "baseline": holdout_base,
            "stress": holdout_stress,
            "all_selected_realized_positive": all_holdout_positive,
            "productive_capacity_gain": holdout_productive,
            "router_events_baseline": holdout_events_base,
            "router_events_stress": holdout_events_stress,
            "pass": holdout_pass,
            "selection_or_retuning_performed": False,
        },
        "full_three_year_rejection_check": {
            "baseline_vs_core": fb,
            "stress_vs_core": fs,
            "baseline": full_base,
            "stress": full_stress,
            "pass": full_pass,
            "selection_or_retuning_performed": False,
        },
        "step5b_pass": step5b_pass,
        "selected_for_step6_robustness": list(frozen_subset) if step5b_pass else [],
        "next_stage": (
            "STEP6_ROUTER_AWARE_SATELLITE_ROBUSTNESS"
            if step5b_pass
            else "STEP5B_REPAIR_OR_BOUNDED_FILLER_EXIT_HYPOTHESIS"
        ),
        "provenance_by_symbol": provenance,
        "safety": {
            "product_runner_modified": False,
            "satellites_never_preempt_open_core": True,
            "satellite_max_slots_each": 1,
            "router_calibration_training_only": True,
            "holdout_rejection_only": True,
            "future_realized_outcome_used_for_decision": False,
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "study": output["study"],
                "frozen_router": output["frozen_router"],
                "training_selected_satellites": list(frozen_subset),
                "holdout_pass": holdout_pass,
                "full_three_year_pass": full_pass,
                "step5b_pass": step5b_pass,
                "selected_for_step6_robustness": output[
                    "selected_for_step6_robustness"
                ],
                "holdout_baseline_vs_core": hb,
                "holdout_stress_vs_core": hs,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Shared 250-USDC Core+Satellite portfolio engine for the 15-market candidate.

Core signals have absolute priority. Satellites are one-slot gap fillers and may
consume only otherwise-free capacity. Any executable Core entry reclaims enough
Satellite slots at the next executable open to restore the canonical Core allocation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from hixton.backtest.engine import candle_snapshot_sha256
from hixton.backtest.metrics import calculate_metrics
from hixton.backtest.models import (
    ONE,
    ZERO,
    CostModel,
    EquityPoint,
    ExecutionRules,
    Fill,
    PortfolioBacktestResult,
    Trade,
)
from hixton.constants import TIMEFRAME_DELTA
from hixton.data.quality import audit_candles
from hixton.domain.allocation import RANKED_REPEAT, allocate_entry_slots
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

D = Decimal
HUNDRED = D("100")
VERSION = "HIXTON-V6-SATELLITE-15-CANDIDATE-1"
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
    satellite_budget_fraction_of_c: Decimal

    @property
    def key(self) -> str:
        return (
            f"h{self.filler_horizon_hours}_m{self.hysteresis_atr}"
            f"_s{self.satellite_budget_fraction_of_c}"
        )


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
    horizon_hours: int | None = None,
) -> Decimal:
    """Score remaining filler value from entry strength, age and live trend."""

    entry_strength = max(D("0"), _d(trade.signal.breakout_strength or 0))
    age_hours = max(
        D("0"),
        D(str((at - trade.fill.fill_time_utc).total_seconds() / 3600)),
    )
    horizon = D(horizon_hours or config.filler_horizon_hours)
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
    strategy_semantics_by_symbol: dict[str, StrategySemantics] | None = None,
    strict_core_idle_mask: bool = False,
    soft_filler_exit_enabled: bool = True,
    soft_filler_exit_symbols: frozenset[str] | None = None,
    entry_filter_by_symbol: dict[str, Callable[[IndicatorPoint], str | None]] | None = None,
    continuation_reentry_symbols: frozenset[str] | None = None,
    band_reentry_symbols: frozenset[str] | None = None,
    atr_reentry_level_by_symbol: dict[str, float] | None = None,
    entry_atr_direction_by_symbol: dict[str, str] | None = None,
    trend_health_exit_by_symbol: dict[str, float] | None = None,
    profit_take_atr_by_symbol: dict[str, float] | None = None,
    filler_horizon_hours_by_symbol: dict[str, int] | None = None,
    satellite_max_portfolio_drawdown_pct: Decimal | None = None,
) -> tuple[PortfolioBacktestResult, list[dict[str, object]]]:
    if tuple(candles_by_symbol) != symbols:
        raise ValueError("router input universe/order mismatch")
    if set(strategy_parameters_by_symbol) != set(symbols):
        raise ValueError("router parameters must cover the full research universe")
    if set(trade_policies_by_symbol) != set(symbols):
        raise ValueError("router policies must cover the full research universe")
    if (
        strategy_semantics_by_symbol is not None
        and set(strategy_semantics_by_symbol) != set(symbols)
    ):
        raise ValueError("router semantics must cover the full research universe")
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
            semantics=(
                V6_COIN_STRATEGY.semantics
                if strategy_semantics_by_symbol is None
                else strategy_semantics_by_symbol[symbol]
            ),
            strategy_version=VERSION,
        )
        for symbol in symbols
    }
    gates = {
        symbol: TradePolicyGate(trade_policies_by_symbol[symbol]) for symbol in symbols
    }
    core_set = frozenset(core_symbols)
    satellite_set = frozenset(satellite_symbols)
    entry_filters = entry_filter_by_symbol or {}
    soft_exit_symbols = (
        frozenset(satellite_symbols)
        if soft_filler_exit_symbols is None
        else soft_filler_exit_symbols
    )
    continuation_reentry = continuation_reentry_symbols or frozenset()
    band_reentry = band_reentry_symbols or frozenset()
    atr_reentry_levels = atr_reentry_level_by_symbol or {}
    atr_directions = entry_atr_direction_by_symbol or {}
    trend_health_exits = trend_health_exit_by_symbol or {}
    profit_take_levels = profit_take_atr_by_symbol or {}
    filler_horizons = filler_horizon_hours_by_symbol or {}
    if not set(entry_filters).issubset(set(symbols)):
        raise ValueError("entry filters reference symbols outside the candidate universe")
    if not set(soft_exit_symbols).issubset(set(satellite_symbols)):
        raise ValueError("soft filler exits are Satellite-only")
    if not set(continuation_reentry).issubset(set(satellite_symbols)):
        raise ValueError("continuation re-entry is research-only and Satellite-only")
    if not set(band_reentry).issubset(set(satellite_symbols)):
        raise ValueError("band re-entry is research-only and Satellite-only")
    if not set(atr_reentry_levels).issubset(set(satellite_symbols)):
        raise ValueError("ATR-level re-entry is research-only and Satellite-only")
    if not set(atr_directions).issubset(set(symbols)):
        raise ValueError("ATR-direction filters reference symbols outside the research universe")
    if any(value not in {"EXPANDING", "CONTRACTING"} for value in atr_directions.values()):
        raise ValueError("ATR-direction must be EXPANDING or CONTRACTING")
    if not set(trend_health_exits).issubset(set(satellite_symbols)):
        raise ValueError("trend-health exits are research-only and Satellite-only")
    if not set(profit_take_levels).issubset(set(satellite_symbols)):
        raise ValueError("profit-take exits are research-only and Satellite-only")
    if any(value <= 0 or value > 20 for value in profit_take_levels.values()):
        raise ValueError("profit-take ATR thresholds must be in (0, 20]")
    if not set(filler_horizons).issubset(set(satellite_symbols)):
        raise ValueError("filler horizons are Satellite-only")
    if any(type(value) is not int or value <= 0 for value in filler_horizons.values()):
        raise ValueError("per-Satellite filler horizons must be positive integers")
    if (
        satellite_max_portfolio_drawdown_pct is not None
        and (
            satellite_max_portfolio_drawdown_pct < ZERO
            or satellite_max_portfolio_drawdown_pct > HUNDRED
        )
    ):
        raise ValueError("Satellite portfolio drawdown gate must be in [0, 100]")

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
    current_drawdown_pct = ZERO

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

    def open_position(
        signal: Signal,
        *,
        slots: int,
        at: datetime,
        candle: Candle,
        budget_override: Decimal | None = None,
    ) -> bool:
        nonlocal cash
        if slots <= 0 or signal.symbol in positions:
            return False
        rule = execution_rules[signal.symbol]
        budget = min(
            budget_override if budget_override is not None else target_notional * D(slots),
            cash,
        )
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
                if (
                    not close_position(
                        signal.symbol,
                        at=open_time,
                        candle=candles[signal.symbol],
                        reason_id=signal.signal_id,
                    )
                    and signal.symbol not in positions
                ):
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
                    if strict_core_idle_mask:
                        sat_symbol, _sat_trade = sorted(
                            candidates, key=lambda item: item[0]
                        )[0]
                        router_events.append(
                            {
                                "time_utc": open_time.isoformat(),
                                "satellite_symbol": sat_symbol,
                                "core_candidate": core_signal.symbol,
                                "desired_core_slots": desired_slots,
                                "decision": "STRICT_IDLE_HANDOFF",
                            }
                        )
                        close_position(
                            sat_symbol,
                            at=open_time,
                            candle=candles[sat_symbol],
                            reason_id=f"STRICT_IDLE_HANDOFF::{core_signal.signal_id}",
                        )
                        continue

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
                            horizon_hours=filler_horizons.get(symbol),
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

            # Satellites are strict gap-fillers: they may enter only when the Core
            # engine is completely idle. This isolates the owner's intended use-case
            # (monetize the quiet gap between Core trades) instead of treating a spare
            # second slot during an active Core position as Satellite capacity.
            core_active = any(not trade.is_satellite for trade in positions.values())
            if strict_core_idle_mask and core_active:
                for sat_symbol in sorted(
                    symbol
                    for symbol, trade in positions.items()
                    if trade.is_satellite
                ):
                    close_position(
                        sat_symbol,
                        at=open_time,
                        candle=candles[sat_symbol],
                        reason_id="STRICT_CORE_IDLE_MASK",
                    )
            core_active = any(not trade.is_satellite for trade in positions.values())
            for signal in satellite_entries:
                if signal.symbol in positions:
                    blocked.append(f"{signal.signal_id}:POSITION_ALREADY_OPEN")
                    continue
                if core_active:
                    blocked.append(f"{signal.signal_id}:CORE_ACTIVE_FILLER_IDLE_ONLY")
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
                    budget_override=(
                        starting_cash * router_config.satellite_budget_fraction_of_c
                    ),
                )
            pending = []

        points: dict[str, IndicatorPoint] = {}
        previous_points: dict[str, IndicatorPoint | None] = {}
        decisions = {}
        for symbol in symbols:
            previous_point = last_points.get(symbol)
            previous_points[symbol] = previous_point
            point = strategies[symbol].update(candles[symbol])
            points[symbol] = point
            position = positions.get(symbol)
            if position is not None:
                position.highest_close = max(position.highest_close, candles[symbol].close)
            decisions[symbol] = gates[symbol].decide(
                point,
                entry_price=float(position.fill.fill_price) if position else None,
                entry_atr=position.signal.atr if position else 0.0,
                highest_close=position.highest_close if position else 0.0,
            )

            # Research-only continuation entry overlay. This creates a new opportunity
            # only after a completed pullback through VIDYA while the canonical trend
            # remains UP. It uses current/prior closed bars only and leaves product
            # strategy semantics untouched.
            if (
                in_report
                and symbol in continuation_reentry
                and position is None
                and decisions[symbol].signal is None
                and previous_point is not None
                and point.trend.value == "UP"
                and previous_point.vidya is not None
                and point.vidya is not None
                and previous_point.candle.close <= previous_point.vidya
                and point.candle.close > point.vidya
            ):
                synthetic = HixtonStrategy.signal_for(
                    replace(point, flip_up=True, flip_down=False),
                    is_long=False,
                )
                if synthetic is not None:
                    decisions[symbol] = replace(
                        decisions[symbol],
                        signal=synthetic,
                        exit_reason="RESEARCH_CONTINUATION_REENTRY",
                    )

            # Stricter research-only continuation: after a pullback below the
            # upper VIDYA/ATR band, allow a fresh entry only when the next closed bar
            # reclaims that upper band while the canonical trend is still UP.
            if (
                in_report
                and symbol in band_reentry
                and position is None
                and decisions[symbol].signal is None
                and previous_point is not None
                and point.trend.value == "UP"
                and previous_point.upper is not None
                and point.upper is not None
                and previous_point.candle.close <= previous_point.upper
                and point.candle.close > point.upper
            ):
                synthetic = HixtonStrategy.signal_for(
                    replace(point, flip_up=True, flip_down=False),
                    is_long=False,
                )
                if synthetic is not None:
                    decisions[symbol] = replace(
                        decisions[symbol],
                        signal=synthetic,
                        exit_reason="RESEARCH_UPPER_BAND_REENTRY",
                    )

            # Intermediate ATR-level continuation re-entry. Unlike the broad VIDYA
            # cross and strict upper-band cross, this can require a configurable
            # point-in-time reclaim level such as VIDYA + 0.5*ATR.
            atr_level = atr_reentry_levels.get(symbol)
            if (
                in_report
                and atr_level is not None
                and position is None
                and decisions[symbol].signal is None
                and previous_point is not None
                and point.trend.value == "UP"
                and previous_point.vidya is not None
                and previous_point.atr is not None
                and point.vidya is not None
                and point.atr is not None
                and previous_point.atr > 0
                and point.atr > 0
            ):
                previous_threshold = previous_point.vidya + float(atr_level) * previous_point.atr
                current_threshold = point.vidya + float(atr_level) * point.atr
                if (
                    previous_point.candle.close <= previous_threshold
                    and point.candle.close > current_threshold
                ):
                    synthetic = HixtonStrategy.signal_for(
                        replace(point, flip_up=True, flip_down=False),
                        is_long=False,
                    )
                    if synthetic is not None:
                        decisions[symbol] = replace(
                            decisions[symbol],
                            signal=synthetic,
                            exit_reason="RESEARCH_ATR_LEVEL_REENTRY",
                        )

            last_points[symbol] = point

            # Point-in-time research-only profit take. Use the CLOSED candle
            # and the entry signal ATR, then schedule the exit for the next open.
            # This deliberately avoids intrabar highs and therefore does not add
            # optimistic lookahead to short-horizon filler research.
            profit_take_atr = profit_take_levels.get(symbol)
            if (
                in_report
                and profit_take_atr is not None
                and position is not None
                and position.is_satellite
                and decisions[symbol].signal is None
                and position.signal.atr > 0
            ):
                entry_price = float(position.fill.fill_price)
                profit_atr = (point.candle.close - entry_price) / position.signal.atr
                if profit_atr >= float(profit_take_atr):
                    forced = HixtonStrategy.signal_for(
                        replace(point, flip_down=True, flip_up=False),
                        is_long=True,
                    )
                    if forced is not None:
                        decisions[symbol] = replace(
                            decisions[symbol],
                            signal=forced,
                            exit_reason="RESEARCH_PROFIT_TAKE_ATR",
                        )

            # Point-in-time research exit when trend health degrades below a
            # training-selected threshold. This is separate from the existing
            # max-hold/value-decay exit and never mutates product strategy code.
            trend_exit = trend_health_exits.get(symbol)
            if (
                in_report
                and trend_exit is not None
                and position is not None
                and position.is_satellite
                and decisions[symbol].signal is None
                and point.vidya is not None
                and point.atr is not None
                and point.atr > 0
            ):
                trend_health = (point.candle.close - point.vidya) / point.atr
                if trend_health <= float(trend_exit):
                    forced = HixtonStrategy.signal_for(
                        replace(point, flip_down=True, flip_up=False),
                        is_long=True,
                    )
                    if forced is not None:
                        decisions[symbol] = replace(
                            decisions[symbol],
                            signal=forced,
                            exit_reason="RESEARCH_TREND_HEALTH_EXIT",
                        )

            # Soft short-horizon filler exit: if the training-calibrated remaining-value
            # score has fully decayed and the canonical strategy has not already exited,
            # schedule an exit for the next open.
            if (
                soft_filler_exit_enabled
                and symbol in soft_exit_symbols
                and in_report
                and position is not None
                and position.is_satellite
                and decisions[symbol].signal is None
            ):
                horizon_hours = filler_horizons.get(symbol, router_config.filler_horizon_hours)
                remaining = _remaining_satellite_score(
                    trade=position,
                    point=point,
                    at=point.candle.close_time_utc,
                    config=router_config,
                    horizon_hours=horizon_hours,
                )
                age_hours = (
                    point.candle.close_time_utc - position.fill.fill_time_utc
                ).total_seconds() / 3600
                if age_hours >= horizon_hours and remaining <= D("0.50"):
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
            current_drawdown_pct = risk.drawdown_pct
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
                    if (
                        symbol in satellite_set
                        and satellite_max_portfolio_drawdown_pct is not None
                        and current_drawdown_pct > satellite_max_portfolio_drawdown_pct
                    ):
                        blocked.append(
                            f"{signal.signal_id}:SATELLITE_PORTFOLIO_DRAWDOWN_GATE"
                        )
                        continue
                    entry_filter = entry_filters.get(symbol)
                    if entry_filter is not None:
                        filter_reason = entry_filter(points[symbol])
                        if filter_reason:
                            blocked.append(f"{signal.signal_id}:{filter_reason}")
                            continue
                    atr_direction = atr_directions.get(symbol)
                    if atr_direction is not None:
                        previous_point = previous_points.get(symbol)
                        current_point = points[symbol]
                        if (
                            previous_point is None
                            or previous_point.atr is None
                            or current_point.atr is None
                        ):
                            blocked.append(f"{signal.signal_id}:ATR_DIRECTION_UNAVAILABLE")
                            continue
                        if atr_direction == "EXPANDING" and current_point.atr <= previous_point.atr:
                            blocked.append(f"{signal.signal_id}:ATR_NOT_EXPANDING")
                            continue
                        if (
                            atr_direction == "CONTRACTING"
                            and current_point.atr >= previous_point.atr
                        ):
                            blocked.append(f"{signal.signal_id}:ATR_NOT_CONTRACTING")
                            continue
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


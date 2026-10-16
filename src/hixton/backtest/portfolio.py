"""Chronological shared-cash max-budget backtest for the canonical ten USDC markets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from hixton.backtest.engine import candle_snapshot_sha256
from hixton.backtest.metrics import calculate_metrics
from hixton.backtest.models import (
    BASELINE_COSTS,
    ONE,
    ZERO,
    CostModel,
    EquityPoint,
    ExecutionRules,
    Fill,
    PortfolioBacktestResult,
    Trade,
)
from hixton.constants import SYMBOLS, TIMEFRAME_DELTA
from hixton.data.quality import audit_candles
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT, allocate_entry_slots
from hixton.domain.capital import DEFAULT_MAX_CAPITAL_USDC, capital_plan
from hixton.domain.diversification import (
    capacity_units,
    distinct_allocations,
    entry_budget,
    next_count,
    trim_quantity,
    trim_signal_id,
)
from hixton.domain.markets import validate_market_symbols
from hixton.domain.models import (
    Candle,
    IndicatorPoint,
    Signal,
    SignalAction,
    StrategyParameters,
    StrategySemantics,
)
from hixton.domain.risk import PortfolioRiskState, evaluate_portfolio_risk
from hixton.domain.satellite_layer import (
    satellite_handoff_symbols,
    shared_satellite_entry_block_reason,
    shared_satellite_horizon_exit,
)
from hixton.domain.spot_autonomy import (
    entry_volatility_fraction,
    marked_portfolio_equity,
    quality_filler_block_reason,
    reinvestment_capital,
    research_slot_allocations,
    size_spot_entry,
)
from hixton.domain.strategy import HixtonStrategy, entry_priority
from hixton.domain.trade_policy import TradePolicy, TradePolicyGate
from hixton.domain.tranche import allocate_tranches, position_units, size_tranche
from hixton.domain.versions import StrategyDefinition

_HUNDRED = Decimal("100")
_DEFAULT_CAPITAL_PLAN = capital_plan(DEFAULT_MAX_CAPITAL_USDC)


@dataclass(slots=True)
class _OpenTrade:
    signal: Signal
    fill: Fill
    quantity: Decimal
    cost_basis: Decimal
    slots: int
    highest_close: float = 0.0
    allocation_units: int = 0


def _d(value: float) -> Decimal:
    return Decimal(str(value))


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= ZERO:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _equal_weight_buy_and_hold(
    candles_by_symbol: dict[str, list[Candle]],
    starting_cash: Decimal,
    costs: CostModel,
) -> Decimal:
    symbols = tuple(candles_by_symbol)
    allocation = starting_cash / Decimal(len(symbols))
    ending = ZERO
    for symbol in symbols:
        candles = candles_by_symbol[symbol]
        entry = _d(candles[0].open) * (ONE + costs.adverse_price_rate)
        net_quantity = allocation / entry * (ONE - costs.fee_rate)
        ending += net_quantity * _d(candles[-1].close)
    return ending


def run_shared_portfolio_backtest(
    *,
    candles_by_symbol: dict[str, list[Candle]],
    report_start_utc: datetime,
    report_end_utc: datetime,
    starting_cash: Decimal = DEFAULT_MAX_CAPITAL_USDC,
    target_notional: Decimal = _DEFAULT_CAPITAL_PLAN.target_notional_usdc,
    slot_count: int = _DEFAULT_CAPITAL_PLAN.slot_count,
    costs: CostModel = BASELINE_COSTS,
    execution_rules: dict[str, ExecutionRules] | None = None,
    strategy_parameters: StrategyParameters | None = None,
    strategy_parameters_by_symbol: dict[str, StrategyParameters] | None = None,
    trade_policies_by_symbol: dict[str, TradePolicy] | None = None,
    strategy_semantics: StrategySemantics = StrategySemantics.DMS_V1,
    strategy_version: str | None = None,
    slot_allocation: str = RANKED_REPEAT,
    apply_risk_limits: bool = True,
    symbols: tuple[str, ...] = SYMBOLS,
    strategy: StrategyDefinition | None = None,
    reinvest_profits: bool = False,
    autonomous_spot: bool = False,
    profit_reinvestment_fraction: Decimal = Decimal("1"),
    capital_exposure_fraction: Decimal = Decimal("1"),
    allowed_entry_symbols: frozenset[str] | None = None,
) -> PortfolioBacktestResult:
    """Replay ten aligned markets against one non-compounding shared ledger."""

    reinvestment_capital(
        equity=starting_cash,
        starting_cash=starting_cash,
        profit_fraction=profit_reinvestment_fraction,
    )
    if not capital_exposure_fraction.is_finite() or not Decimal(
        "0"
    ) < capital_exposure_fraction <= Decimal("1"):
        raise ValueError("capital exposure fraction must be in (0,1]")
    if not reinvest_profits and (
        profit_reinvestment_fraction != Decimal("1") or capital_exposure_fraction != Decimal("1")
    ):
        raise ValueError("partial reinvestment requires reinvest_profits")
    if strategy is not None:
        if strategy.capital_exposure_fraction != "1":
            configured_fraction = Decimal(strategy.capital_exposure_fraction)
            if capital_exposure_fraction not in (Decimal("1"), configured_fraction):
                raise ValueError("strategy and research exposure fractions disagree")
            capital_exposure_fraction = configured_fraction
        symbols = strategy.symbols
        strategy_parameters = strategy.parameters
        strategy_parameters_by_symbol = strategy.parameter_map()
        trade_policies_by_symbol = strategy.policy_map()
        strategy_semantics = strategy.semantics
        strategy_version = strategy.version
        slot_allocation = strategy.slot_allocation
    satellite_symbols = frozenset(strategy.satellite_symbols if strategy else ())
    active_satellites = frozenset(strategy.active_shared_satellites if strategy else ())
    core_symbols = frozenset(symbols) - satellite_symbols
    if (strategy_version or "").startswith("HIXTON-V8-") and strategy is None:
        raise ValueError("V8 portfolio requires its complete StrategyDefinition")
    validate_market_symbols(symbols)
    if allowed_entry_symbols is not None and (
        not allowed_entry_symbols or not allowed_entry_symbols.issubset(symbols)
    ):
        raise ValueError("Diagnostic entry restriction requires active strategy symbols")
    if tuple(candles_by_symbol) != symbols:
        raise ValueError("portfolio input must contain all ten symbols in fixed DMS order")
    if autonomous_spot and (
        strategy is None or strategy.key not in ("v8", "v8d", "v8r") or slot_count not in (2, 3, 4)
    ):
        raise ValueError("autonomous spot research requires V8 with 2, 3 or 4 capacity slots")
    if starting_cash <= ZERO or target_notional <= ZERO or slot_count <= 0:
        raise ValueError("portfolio capital and slot_count must be positive")
    if report_start_utc >= report_end_utc:
        raise ValueError("report_start_utc must be before report_end_utc")

    parameters = strategy_parameters or StrategyParameters()
    if trade_policies_by_symbol is not None and set(trade_policies_by_symbol) != set(symbols):
        raise ValueError("trade policies require all ten symbols")
    if any(p != TradePolicy() for p in (trade_policies_by_symbol or {}).values()) and not (
        strategy_version or ""
    ).startswith(("HIXTON-V5-", "HIXTON-V6-", "HIXTON-V7-", "HIXTON-V8-")):
        raise ValueError(
            "trade policies require an explicit HIXTON-V5 or HIXTON-V6 strategy version"
        )
    policy_gates = {
        symbol: TradePolicyGate((trade_policies_by_symbol or {}).get(symbol)) for symbol in symbols
    }
    if strategy_parameters_by_symbol is not None:
        if set(strategy_parameters_by_symbol) != set(symbols):
            raise ValueError("per-coin parameters require all ten symbols")
        if any(
            p.warmup_bars != parameters.warmup_bars for p in strategy_parameters_by_symbol.values()
        ):
            raise ValueError("per-coin parameters must share the same warmup")
    warmup_start = report_start_utc - parameters.warmup_bars * TIMEFRAME_DELTA
    selected_by_symbol: dict[str, list[Candle]] = {}
    report_by_symbol: dict[str, list[Candle]] = {}
    rules = execution_rules or {}
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
            raise ValueError("portfolio candles are not aligned by open_time_utc")

    strategies = {
        symbol: HixtonStrategy(
            symbol,
            parameters=(strategy_parameters_by_symbol or {}).get(symbol, parameters),
            semantics=strategy.semantics_for(symbol) if strategy else strategy_semantics,
            strategy_version=strategy_version,
        )
        for symbol in symbols
    }
    cash = starting_cash
    positions: dict[str, _OpenTrade] = {}
    dust = dict.fromkeys(symbols, ZERO)
    pending: list[Signal] = []
    signals: list[Signal] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    equity_curve: list[EquityPoint] = []
    blocked: list[str] = []
    max_concurrent = 0
    risk_state = PortfolioRiskState(
        high_water_equity_usdc=starting_cash,
        day_start_equity_usdc=starting_cash,
        day_start_date_utc=report_start_utc.date().isoformat(),
    )
    risk_halted_at: datetime | None = None
    daily_paused_bars = 0
    daily_paused = False
    previous_points: dict[str, IndicatorPoint] = {}
    weighted = strategy is not None and strategy.second_tranche_split_dd_pct is not None
    if weighted and slot_count != 2:
        raise ValueError("conditional second tranche requires two primary tranches")
    closed_equity = starting_cash
    closed_high_water = starting_cash
    diversification_count = 2

    for row in rows:
        open_time = row[0].open_time_utc
        in_report = report_start_utc <= open_time < report_end_utc
        candles = {candle.symbol: candle for candle in row}

        if (
            in_report
            and strategy is not None
            and strategy.diversification_stages
            and previous_points
        ):
            stage_equity = closed_equity if reinvest_profits else min(closed_equity, starting_cash)
            next_slots = next_count(
                strategy.diversification_stages,
                current=diversification_count,
                closed_equity=stage_equity,
            )
            if next_slots > diversification_count:
                diversification_count = next_slots
                regular_exits = {
                    sig.symbol for sig in pending if sig.action is SignalAction.EXIT_LONG
                }
                for sym, trim_position in positions.items():
                    if sym in regular_exits:
                        continue
                    point = previous_points[sym]
                    assert point.candle.closed and point.candle.close_time_utc < open_time
                    trim_position.allocation_units = capacity_units(next_slots)
                    trim_position.slots = 1
                    rule = rules.get(sym, ExecutionRules())
                    quantity = trim_quantity(
                        owned=trim_position.quantity,
                        closed_equity=stage_equity,
                        close=_d(point.candle.close),
                        count=next_slots,
                        step=rule.step_size,
                    )
                    reference = _d(candles[sym].open)
                    price = reference * (ONE - costs.adverse_price_rate)
                    gross = quantity * price
                    if quantity <= ZERO or quantity < rule.min_qty or gross < rule.min_notional:
                        continue
                    forced = HixtonStrategy.signal_for(
                        replace(point, flip_down=True, flip_up=False), is_long=True
                    )
                    if forced is None:
                        raise RuntimeError("closed diversification decision unavailable")
                    forced = replace(
                        forced,
                        signal_id=trim_signal_id(sym, next_slots, point.candle.close_time_utc),
                    )
                    basis = trim_position.cost_basis * quantity / trim_position.quantity
                    fee = gross * costs.fee_rate
                    net = gross - fee
                    signals.append(forced)
                    fills.append(
                        Fill(
                            forced.signal_id,
                            SignalAction.EXIT_LONG,
                            open_time,
                            reference,
                            price,
                            quantity,
                            gross,
                            fee,
                            quantity * (reference - price),
                        )
                    )
                    trades.append(
                        Trade(
                            sym,
                            trim_position.signal.signal_id,
                            forced.signal_id,
                            trim_position.fill.fill_time_utc,
                            open_time,
                            basis,
                            net,
                            net - basis,
                            (net - basis) / basis * 100,
                            trim_position.fill.fill_price,
                            price,
                            quantity,
                            ZERO,
                            _d(
                                (open_time - trim_position.fill.fill_time_utc).total_seconds()
                                / 3600
                            ),
                            1,
                        )
                    )
                    cash += net
                    trim_position.quantity -= quantity
                    trim_position.cost_basis -= basis

        if in_report and pending:
            exits = [signal for signal in pending if signal.action is SignalAction.EXIT_LONG]
            entries = [signal for signal in pending if signal.action is SignalAction.ENTER_LONG]

            core_entries = [
                s for s in entries if s.symbol in core_symbols and s.symbol not in positions
            ]
            core_entries.sort(key=lambda s: entry_priority(s.breakout_strength, s.symbol, symbols))
            if satellite_symbols and core_entries and not (apply_risk_limits and daily_paused):
                exit_symbols = {s.symbol for s in exits}
                core_signal = sorted(
                    core_entries,
                    key=lambda s: entry_priority(s.breakout_strength, s.symbol, symbols),
                )[0]
                for symbol in satellite_handoff_symbols(
                    core_entry_count=len(core_entries),
                    position_slots={s: p.slots for s, p in positions.items()},
                    active_satellites=active_satellites,
                    slot_count=slot_count,
                    exiting_symbols=frozenset(exit_symbols),
                ):
                    forced = HixtonStrategy.signal_for(
                        replace(previous_points[symbol], flip_down=True, flip_up=False),
                        is_long=True,
                    )
                    assert forced is not None
                    forced = replace(
                        forced,
                        signal_id=hashlib.sha256(
                            f"CORE_CAPACITY_HANDOFF|{symbol}|{core_signal.signal_id}|{open_time.isoformat()}".encode()
                        ).hexdigest(),
                    )
                    exits.append(forced)
                    signals.append(forced)

            for signal in exits:
                open_trade = positions.get(signal.symbol)
                if open_trade is None:
                    blocked.append(f"{signal.signal_id}:POSITION_ALREADY_CLOSED")
                    continue
                rule = rules.get(signal.symbol, ExecutionRules())
                reference = _d(candles[signal.symbol].open)
                fill_price = reference * (ONE - costs.adverse_price_rate)
                sell_quantity = _round_down(open_trade.quantity, rule.step_size)
                gross_quote = sell_quantity * fill_price
                if sell_quantity < rule.min_qty or gross_quote < rule.min_notional:
                    blocked.append(f"{signal.signal_id}:EXIT_BECAME_DUST")
                    dust[signal.symbol] += open_trade.quantity
                    del positions[signal.symbol]
                    continue
                residual = open_trade.quantity - sell_quantity
                fee_quote = gross_quote * costs.fee_rate
                net_quote = gross_quote - fee_quote
                modeled_adverse = sell_quantity * (reference - fill_price)
                basis_fraction = sell_quantity / open_trade.quantity
                realized_basis = open_trade.cost_basis * basis_fraction
                realized_pnl = net_quote - realized_basis
                fill = Fill(
                    signal_id=signal.signal_id,
                    action=signal.action,
                    fill_time_utc=open_time,
                    reference_open=reference,
                    fill_price=fill_price,
                    base_quantity=sell_quantity,
                    quote_value=gross_quote,
                    fee_quote_equivalent=fee_quote,
                    modeled_spread_slippage=modeled_adverse,
                )
                cash += net_quote
                dust[signal.symbol] += residual
                fills.append(fill)
                holding_hours = Decimal(
                    str((open_time - open_trade.fill.fill_time_utc).total_seconds() / 3_600)
                )
                trades.append(
                    Trade(
                        symbol=signal.symbol,
                        entry_signal_id=open_trade.signal.signal_id,
                        exit_signal_id=signal.signal_id,
                        entry_time_utc=open_trade.fill.fill_time_utc,
                        exit_time_utc=open_time,
                        entry_quote_spend=realized_basis,
                        exit_quote_receive=net_quote,
                        realized_pnl=realized_pnl,
                        realized_return_pct=realized_pnl / realized_basis * _HUNDRED,
                        entry_price=open_trade.fill.fill_price,
                        exit_price=fill_price,
                        sold_base_quantity=sell_quantity,
                        residual_dust_quantity=residual,
                        holding_hours=holding_hours,
                        slot_count=open_trade.slots,
                    )
                )
                del positions[signal.symbol]

            entries.sort(
                key=lambda signal: entry_priority(signal.breakout_strength, signal.symbol, symbols)
            )
            allocation_policy = slot_allocation
            if satellite_symbols:
                satellites = [s for s in entries if s.symbol in active_satellites]
                core_active = bool(set(positions) & core_symbols)
                if core_entries or core_active:
                    blocked.extend(
                        f"{s.signal_id}:CORE_ACTIVE_FILLER_IDLE_ONLY" for s in satellites
                    )
                    entries = core_entries
                else:
                    entries = satellites
                    allocation_policy = ONE_PER_SYMBOL
            # Diagnostic perspective only. All fifteen real histories still drive
            # indicators, Core priority and quality gates; allocation may open
            # only the selected coin. Production calls leave this restriction unset.
            if allowed_entry_symbols is not None:
                entries = [s for s in entries if s.symbol in allowed_entry_symbols]
            used_slots = sum(position.slots for position in positions.values())
            split = False
            if weighted:
                assert strategy is not None and strategy.second_tranche_split_dd_pct is not None
                occupied = sum(
                    position_units(p.slots, p.allocation_units) for p in positions.values()
                )
                allocations, split = allocate_tranches(
                    [s.symbol for s in entries if s.symbol not in positions],
                    free_units=max(0, 20 - occupied),
                    policy=allocation_policy,
                    drawdown_pct=(closed_high_water - closed_equity) / closed_high_water * 100,
                    trigger_pct=Decimal(strategy.second_tranche_split_dd_pct),
                    existing_half=len(positions) == 1 and occupied == 10,
                )
            elif autonomous_spot and slot_count > 2:
                allocations = research_slot_allocations(
                    [
                        (signal.symbol, signal.breakout_strength)
                        for signal in entries
                        if signal.symbol not in positions
                    ],
                    free_slots=max(0, slot_count - used_slots),
                    satellite_symbols=satellite_symbols,
                )
            else:
                allocations = allocate_entry_slots(
                    [signal.symbol for signal in entries if signal.symbol not in positions],
                    free_slots=max(0, slot_count - used_slots),
                    policy=allocation_policy,
                )
            if diversification_count > 2:
                occupied = sum(
                    position_units(p.slots, p.allocation_units) for p in positions.values()
                )
                allocations = distinct_allocations(
                    [sig.symbol for sig in entries],
                    owned=tuple(positions),
                    occupied_units=occupied,
                    count=diversification_count,
                )
                split = True
            for signal in entries:
                if satellite_symbols and apply_risk_limits and daily_paused:
                    blocked.append(f"{signal.signal_id}:DAILY_LOSS_5_PERCENT")
                    continue
                if signal.symbol in positions:
                    blocked.append(f"{signal.signal_id}:POSITION_ALREADY_OPEN")
                    continue
                allocated_slots = (
                    allocations.get(signal.symbol, 0)
                    if autonomous_spot and slot_count > 2
                    else (
                        int(sum(position.slots for position in positions.values()) < slot_count)
                        if allocation_policy == ONE_PER_SYMBOL
                        else allocations.get(signal.symbol, 0)
                    )
                )
                allocation_units = 0
                if weighted:
                    allocation_units = allocations.get(signal.symbol, 0)
                    if not split and allocation_policy == ONE_PER_SYMBOL:
                        remaining = 20 - sum(
                            position_units(p.slots, p.allocation_units) for p in positions.values()
                        )
                        allocation_units = min(10, max(0, remaining))
                    allocated_slots = (allocation_units + 9) // 10
                if allocated_slots == 0:
                    blocked.append(f"{signal.signal_id}:NO_FREE_SLOT")
                    continue
                rule = rules.get(signal.symbol, ExecutionRules())
                entry_fraction = entry_volatility_fraction(
                    atr=_d(signal.atr),
                    reference_close=_d(signal.close),
                    target_atr_fraction=(
                        Decimal(strategy.entry_atr_target_fraction)
                        if strategy and strategy.entry_atr_target_fraction
                        else None
                    ),
                    capital_fraction=capital_exposure_fraction,
                )
                if reinvest_profits:
                    price_marks = {symbol: _d(candles[symbol].open) for symbol in symbols}
                    equity_at_open = marked_portfolio_equity(
                        free_quote=cash,
                        base_quantities={symbol: p.quantity for symbol, p in positions.items()},
                        dust_quantities=dust,
                        open_prices=price_marks,
                    )
                    budget = size_spot_entry(
                        equity=reinvestment_capital(
                            equity=equity_at_open,
                            starting_cash=starting_cash,
                            profit_fraction=profit_reinvestment_fraction,
                        ),
                        free_quote=cash,
                        slots=slot_count,
                        allocated_slots=allocated_slots,
                        reserve_fraction=Decimal("1") - entry_fraction,
                    )
                else:
                    budget = min(target_notional * Decimal(allocated_slots) * entry_fraction, cash)
                if weighted:
                    budget = (
                        size_tranche(
                            equity=reinvestment_capital(
                                equity=equity_at_open,
                                starting_cash=starting_cash,
                                profit_fraction=profit_reinvestment_fraction,
                            ),
                            free_quote=cash,
                            units=allocation_units,
                            entry_fraction=entry_fraction,
                        )
                        if reinvest_profits
                        else min(
                            target_notional * Decimal(allocation_units) / 10 * entry_fraction,
                            cash,
                        )
                    )
                if diversification_count > 2:
                    budget = entry_budget(
                        equity=equity_at_open if reinvest_profits else starting_cash,
                        free_quote=cash,
                        count=diversification_count,
                        entry_fraction=entry_fraction,
                    )
                reference = _d(candles[signal.symbol].open)
                fill_price = reference * (ONE + costs.adverse_price_rate)
                gross_quantity = _round_down(budget / fill_price, rule.step_size)
                quote_spend = min(gross_quantity * fill_price, budget)
                if gross_quantity < rule.min_qty or quote_spend < rule.min_notional:
                    blocked.append(f"{signal.signal_id}:BELOW_EXCHANGE_MINIMUM")
                    continue
                if quote_spend <= ZERO or quote_spend > cash:
                    blocked.append(f"{signal.signal_id}:INSUFFICIENT_CASH")
                    continue
                fee_base = gross_quantity * costs.fee_rate
                net_quantity = gross_quantity - fee_base
                fee_quote = fee_base * fill_price
                modeled_adverse = gross_quantity * (fill_price - reference)
                fill = Fill(
                    signal_id=signal.signal_id,
                    action=signal.action,
                    fill_time_utc=open_time,
                    reference_open=reference,
                    fill_price=fill_price,
                    base_quantity=net_quantity,
                    quote_value=quote_spend,
                    fee_quote_equivalent=fee_quote,
                    modeled_spread_slippage=modeled_adverse,
                )
                cash -= quote_spend
                positions[signal.symbol] = _OpenTrade(
                    signal,
                    fill,
                    net_quantity,
                    quote_spend,
                    allocated_slots,
                    float(fill_price),
                    allocation_units,
                )
                fills.append(fill)
            pending = []

        points = {}
        decisions = {}
        for symbol in symbols:
            points[symbol] = strategies[symbol].update(candles[symbol])
            position = positions.get(symbol)
            if position is not None:
                position.highest_close = max(position.highest_close, candles[symbol].close)
            decisions[symbol] = policy_gates[symbol].decide(
                points[symbol],
                entry_price=float(position.fill.fill_price) if position else None,
                entry_atr=position.signal.atr if position else 0.0,
                highest_close=position.highest_close if position else 0.0,
            )
            if position and symbol in active_satellites and decisions[symbol].signal is None:
                horizon_signal = shared_satellite_horizon_exit(
                    symbol, points[symbol], entry_time_utc=position.fill.fill_time_utc
                )
                if horizon_signal is not None:
                    decisions[symbol] = replace(decisions[symbol], signal=horizon_signal)
        previous_points = points
        if in_report:
            max_concurrent = max(
                max_concurrent,
                (
                    len(positions)
                    if weighted
                    else sum(position.slots for position in positions.values())
                ),
            )
            position_value = sum(
                (
                    ((positions[symbol].quantity if symbol in positions else ZERO) + dust[symbol])
                    * _d(candles[symbol].close)
                    for symbol in symbols
                ),
                ZERO,
            )
            equity = cash + position_value
            closed_equity = equity
            closed_high_water = max(closed_high_water, equity)
            daily_paused = False
            if apply_risk_limits:
                decision = evaluate_portfolio_risk(
                    risk_state,
                    equity=equity,
                    at=max(candle.close_time_utc for candle in row),
                )
                if not risk_state.halted and decision.state.halted:
                    risk_halted_at = max(candle.close_time_utc for candle in row)
                risk_state = decision.state
                daily_paused = decision.daily_paused
                daily_paused_bars += int(daily_paused)

            new_pending: list[Signal] = []
            for symbol in symbols:
                new_signal = decisions[symbol].signal
                if new_signal is None:
                    continue
                signals.append(new_signal)
                if decisions[symbol].block_reason:
                    blocked.append(f"{new_signal.signal_id}:{decisions[symbol].block_reason}")
                    continue
                if new_signal.action is SignalAction.ENTER_LONG and symbol in satellite_symbols:
                    reason = shared_satellite_entry_block_reason(symbol, points[symbol])
                    if reason is None and autonomous_spot:
                        reason = quality_filler_block_reason(symbol, points[symbol].abs_cmo)
                    if reason is not None:
                        blocked.append(f"{new_signal.signal_id}:{reason}")
                        continue
                if (
                    new_signal.action is SignalAction.ENTER_LONG
                    and apply_risk_limits
                    and not satellite_symbols
                ):
                    if risk_state.halted:
                        blocked.append(
                            f"{new_signal.signal_id}:{risk_state.halt_reason or 'HALTED'}"
                        )
                        continue
                    if daily_paused:
                        blocked.append(f"{new_signal.signal_id}:DAILY_LOSS_5_PERCENT")
                        continue
                new_pending.append(new_signal)
            pending = new_pending
            equity_curve.append(
                EquityPoint(
                    time_utc=max(candle.close_time_utc for candle in row),
                    cash=cash,
                    position_value=position_value,
                    equity=equity,
                    active_position=bool(positions),
                )
            )

    if not equity_curve:
        raise ValueError("report window did not contain candles")
    metrics = calculate_metrics(
        starting_equity=starting_cash,
        ending_equity=equity_curve[-1].equity,
        report_start_utc=report_start_utc,
        report_end_utc=report_end_utc,
        trades=tuple(trades),
        fills=tuple(fills),
        equity_curve=tuple(equity_curve),
        buy_and_hold_ending_equity=_equal_weight_buy_and_hold(
            report_by_symbol, starting_cash, costs
        ),
    )
    return PortfolioBacktestResult(
        symbols=symbols,
        report_start_utc=report_start_utc,
        report_end_utc=report_end_utc,
        warmup_start_utc=warmup_start,
        cost_model=costs,
        starting_cash=starting_cash,
        target_notional=target_notional,
        slot_count=slot_count,
        slot_allocation=slot_allocation,
        signals=tuple(signals),
        fills=tuple(fills),
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
        blocked_signals=tuple(blocked),
        pending_signals_at_end=tuple(pending),
        open_symbols_at_end=tuple(symbol for symbol in symbols if symbol in positions),
        dust_quantity_by_symbol=dust,
        max_concurrent_positions=max_concurrent,
        risk_limits_applied=apply_risk_limits,
        risk_halted_at_utc=risk_halted_at,
        daily_paused_bars=daily_paused_bars,
        metrics=metrics,
        data_snapshot_sha256_by_symbol={
            symbol: candle_snapshot_sha256(selected_by_symbol[symbol]) for symbol in symbols
        },
    )


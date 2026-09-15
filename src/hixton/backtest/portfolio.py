"""Chronological shared-cash 3x80 portfolio backtest for all DMS markets."""

from __future__ import annotations

from dataclasses import dataclass
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
from hixton.domain.allocation import ONE_PER_SYMBOL, allocate_entry_slots
from hixton.domain.markets import validate_market_symbols
from hixton.domain.models import Candle, Signal, SignalAction, StrategyParameters, StrategySemantics
from hixton.domain.risk import PortfolioRiskState, evaluate_portfolio_risk
from hixton.domain.strategy import HixtonStrategy, entry_priority
from hixton.domain.trade_policy import TradePolicy, TradePolicyGate

_HUNDRED = Decimal("100")


@dataclass(slots=True)
class _OpenTrade:
    signal: Signal
    fill: Fill
    quantity: Decimal
    cost_basis: Decimal
    slots: int
    highest_close: float = 0.0


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
    starting_cash: Decimal = Decimal("240.00"),
    target_notional: Decimal = Decimal("80.00"),
    slot_count: int = 3,
    costs: CostModel = BASELINE_COSTS,
    execution_rules: dict[str, ExecutionRules] | None = None,
    strategy_parameters: StrategyParameters | None = None,
    strategy_parameters_by_symbol: dict[str, StrategyParameters] | None = None,
    trade_policies_by_symbol: dict[str, TradePolicy] | None = None,
    strategy_semantics: StrategySemantics = StrategySemantics.DMS_V1,
    strategy_version: str | None = None,
    slot_allocation: str = ONE_PER_SYMBOL,
    apply_risk_limits: bool = True,
    symbols: tuple[str, ...] = SYMBOLS,
) -> PortfolioBacktestResult:
    """Replay ten aligned markets against one non-compounding shared ledger."""

    validate_market_symbols(symbols)
    if tuple(candles_by_symbol) != symbols:
        raise ValueError("portfolio input must contain all ten symbols in fixed DMS order")
    if starting_cash <= ZERO or target_notional <= ZERO or slot_count <= 0:
        raise ValueError("portfolio capital and slot_count must be positive")
    if report_start_utc >= report_end_utc:
        raise ValueError("report_start_utc must be before report_end_utc")

    parameters = strategy_parameters or StrategyParameters()
    if trade_policies_by_symbol is not None and set(trade_policies_by_symbol) != set(symbols):
        raise ValueError("trade policies require all ten symbols")
    if any(p != TradePolicy() for p in (trade_policies_by_symbol or {}).values()) and not (
        strategy_version or ""
    ).startswith(("HIXTON-V5-", "HIXTON-V6-", "HIXTON-V7-")):
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
            semantics=strategy_semantics,
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

    for row in rows:
        open_time = row[0].open_time_utc
        in_report = report_start_utc <= open_time < report_end_utc
        candles = {candle.symbol: candle for candle in row}

        if in_report and pending:
            exits = [signal for signal in pending if signal.action is SignalAction.EXIT_LONG]
            entries = [signal for signal in pending if signal.action is SignalAction.ENTER_LONG]

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
                    )
                )
                del positions[signal.symbol]

            entries.sort(
                key=lambda signal: entry_priority(signal.breakout_strength, signal.symbol, symbols)
            )
            used_slots = sum(position.slots for position in positions.values())
            allocations = allocate_entry_slots(
                [signal.symbol for signal in entries if signal.symbol not in positions],
                free_slots=max(0, slot_count - used_slots),
                policy=slot_allocation,
            )
            for signal in entries:
                if signal.symbol in positions:
                    blocked.append(f"{signal.signal_id}:POSITION_ALREADY_OPEN")
                    continue
                allocated_slots = (
                    int(sum(position.slots for position in positions.values()) < slot_count)
                    if slot_allocation == ONE_PER_SYMBOL
                    else allocations.get(signal.symbol, 0)
                )
                if allocated_slots == 0:
                    blocked.append(f"{signal.signal_id}:NO_FREE_SLOT")
                    continue
                rule = rules.get(signal.symbol, ExecutionRules())
                budget = min(target_notional * Decimal(allocated_slots), cash)
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
        if in_report:
            max_concurrent = max(
                max_concurrent,
                sum(position.slots for position in positions.values()),
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
                if new_signal.action is SignalAction.ENTER_LONG and apply_risk_limits:
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

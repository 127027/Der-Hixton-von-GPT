"""Deterministic shared-cash paper execution for closed Hixton bars."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from hixton.backtest.models import BASELINE_COSTS, ONE, ZERO, ExecutionRules
from hixton.constants import HIXTON_SPEC_VERSION, SYMBOLS
from hixton.domain.models import Candle, IndicatorPoint, Signal, SignalAction
from hixton.domain.risk import PortfolioRiskState, evaluate_portfolio_risk
from hixton.domain.strategy import entry_priority
from hixton.domain.trade_policy import TradePolicy, TradePolicyGate
from hixton.domain.versions import StrategyDefinition
from hixton.paper.models import (
    PaperAccount,
    PaperEvent,
    PaperEventStatus,
    PaperPortfolio,
    PaperPosition,
)
from hixton.paper.storage import PaperStore

_HUNDRED = Decimal("100")


def _d(value: float) -> Decimal:
    return Decimal(str(value))


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= ZERO:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _event_id(signal: Signal) -> str:
    return hashlib.sha256(f"PAPER|{signal.signal_id}".encode()).hexdigest()


def initialize_paper_at_latest(
    database_path: str,
    points_by_symbol: Mapping[str, tuple[IndicatorPoint, ...]],
    *,
    at: datetime | None = None,
    strategy_key: str = "v1",
    strategy_version: str = HIXTON_SPEC_VERSION,
    starting_cash_usdc: Decimal | None = None,
) -> bool:
    """Arm a new account at latest; preserve checkpoints on every later restart."""

    if set(points_by_symbol) != set(SYMBOLS):
        raise ValueError("paper initialization requires all ten DMS symbols")
    checkpoints: dict[str, datetime] = {}
    for symbol in SYMBOLS:
        points = points_by_symbol[symbol]
        if not points:
            raise ValueError(f"cannot initialize paper without candles for {symbol}")
        checkpoints[symbol] = points[-1].candle.close_time_utc
    with PaperStore(database_path) as store:
        store.initialize(
            at=at,
            strategy_key=strategy_key,
            strategy_version=strategy_version,
            starting_cash_usdc=starting_cash_usdc,
        )
        store.require_strategy(strategy_key, strategy_version)
        existing = store.all_checkpoints()
        if existing and set(existing) != set(SYMBOLS):
            raise RuntimeError("paper checkpoints are incomplete; recovery must fail closed")
        first_start = not existing
        if first_start:
            store.save_checkpoints(checkpoints)
            existing = checkpoints
        store.ensure_soak_started(existing, at=at)
        store.ensure_execution_epoch(existing, at=at)
    return first_start


def _blocked_event(signal: Signal, reason: str) -> PaperEvent:
    return PaperEvent(
        event_id=_event_id(signal),
        signal_id=signal.signal_id,
        occurred_at_utc=signal.candle_close_time_utc,
        symbol=signal.symbol,
        action=signal.action.value,
        status=PaperEventStatus.BLOCKED,
        reason=reason,
        reference_price=_d(signal.close),
        execution_price=None,
        base_quantity=None,
        quote_amount_usdc=None,
        fee_usdc=None,
        realized_pnl_usdc=None,
        breakout_strength=(
            _d(signal.breakout_strength) if signal.breakout_strength is not None else None
        ),
        strategy_version=signal.strategy_version,
    )


def _equity(
    cash: Decimal,
    positions: Mapping[str, PaperPosition],
    latest_prices: Mapping[str, Decimal],
    dust: Mapping[str, Decimal] | None = None,
) -> tuple[Decimal, Decimal]:
    market_value = sum(
        (
            position.quantity * latest_prices.get(symbol, position.average_price)
            for symbol, position in positions.items()
        ),
        ZERO,
    )
    basis = sum((position.cost_basis_usdc for position in positions.values()), ZERO)
    dust_value = sum(
        (qty * latest_prices.get(symbol, ZERO) for symbol, qty in (dust or {}).items()), ZERO
    )
    return cash + market_value + dust_value, market_value - basis


def _risk_account(
    account: PaperAccount,
    *,
    equity: Decimal,
    at: datetime,
) -> tuple[PaperAccount, bool, Decimal]:
    decision = evaluate_portfolio_risk(
        PortfolioRiskState(
            high_water_equity_usdc=account.high_water_equity_usdc,
            day_start_equity_usdc=account.day_start_equity_usdc,
            day_start_date_utc=account.day_start_date_utc,
            halted=account.halted,
            halt_reason=account.halt_reason,
        ),
        equity=equity,
        at=at,
    )
    updated = replace(
        account,
        high_water_equity_usdc=decision.state.high_water_equity_usdc,
        day_start_equity_usdc=decision.state.day_start_equity_usdc,
        day_start_date_utc=decision.state.day_start_date_utc,
        halted=decision.state.halted,
        halt_reason=decision.state.halt_reason,
        updated_at_utc=at.astimezone(UTC),
    )
    return updated, decision.daily_paused, decision.drawdown_pct


def process_new_closed_points(
    database_path: str,
    points_by_symbol: Mapping[str, tuple[IndicatorPoint, ...]],
    rules_by_symbol: Mapping[str, ExecutionRules],
    *,
    strategy_key: str = "v1",
    strategy_version: str = HIXTON_SPEC_VERSION,
    execution_candles_by_symbol: Mapping[str, list[Candle]] | None = None,
    trade_policies_by_symbol: Mapping[str, TradePolicy] | None = None,
) -> tuple[PaperEvent, ...]:
    """Process every not-yet-checkpointed bar atomically and exactly once."""

    if set(points_by_symbol) != set(SYMBOLS):
        raise ValueError("paper processing requires all ten DMS symbols")
    if set(rules_by_symbol) != set(SYMBOLS):
        raise ValueError("paper processing requires exchange rules for all symbols")
    if trade_policies_by_symbol is not None and set(trade_policies_by_symbol) != set(SYMBOLS):
        raise ValueError("paper trade policies require all ten symbols")
    if any(
        p != TradePolicy() for p in (trade_policies_by_symbol or {}).values()
    ) and not strategy_version.startswith("HIXTON-V6-"):
        raise ValueError("paper policies require an explicit HIXTON-V6 version")
    if strategy_key == "v6" and trade_policies_by_symbol is None:
        raise ValueError("V6 paper requires its complete coin-policy map")
    policy_gates = {s: TradePolicyGate((trade_policies_by_symbol or {}).get(s)) for s in SYMBOLS}

    with PaperStore(database_path) as store:
        store.initialize(
            strategy_key=strategy_key,
            strategy_version=strategy_version,
        )
        store.require_strategy(strategy_key, strategy_version)
        account = store.load_account()
        settings = store.load_settings()
        positions = {position.symbol: position for position in store.load_positions()}
        dust = store.load_dust()
        checkpoints = store.all_checkpoints()
        if set(checkpoints) != set(SYMBOLS):
            raise RuntimeError("paper checkpoints are incomplete; run startup initialization")
        store.ensure_soak_started(checkpoints)

        pending: dict[datetime, list[IndicatorPoint]] = {}
        processed_bars = dict.fromkeys(SYMBOLS, 0)
        latest_prices: dict[str, Decimal] = {}
        execution = {
            symbol: {candle.open_time_utc: candle for candle in candles}
            for symbol, candles in (
                execution_candles_by_symbol
                or {
                    symbol: [point.candle for point in values]
                    for symbol, values in points_by_symbol.items()
                }
            ).items()
        }
        for symbol in SYMBOLS:
            history = [
                p
                for p in points_by_symbol[symbol]
                if p.candle.close_time_utc <= checkpoints[symbol]
            ]
            policy = (trade_policies_by_symbol or {}).get(symbol, TradePolicy())
            if policy.slope_bars and len(history) < policy.slope_bars:
                raise RuntimeError(f"missing policy warmup history for {symbol}")
            for historical in history[-max(1, policy.slope_bars) :]:
                policy_gates[symbol].decide(historical)
            for point in points_by_symbol[symbol]:
                if point.strategy_version != strategy_version:
                    raise RuntimeError(f"indicator strategy mismatch for {symbol}")
                if point.candle.close_time_utc <= checkpoints[symbol]:
                    latest_prices[symbol] = _d(point.candle.close)
                if point.candle.close_time_utc > checkpoints[symbol]:
                    boundary = point.candle.open_time_utc + timedelta(hours=1)
                    pending.setdefault(boundary, []).append(point)

        emitted: list[PaperEvent] = []
        processed_time: datetime | None = None
        for boundary, group in sorted(pending.items()):
            group_by_symbol = {point.symbol: point for point in group}
            if set(group_by_symbol) != set(SYMBOLS):
                raise RuntimeError("paper replay requires aligned bars for all ten symbols")
            # Keep the last bar pending until the true next-bar OPEN is available.
            if any(boundary not in execution.get(symbol, {}) for symbol in SYMBOLS):
                break
            fill_candles = {symbol: execution[symbol][boundary] for symbol in SYMBOLS}
            if any(not candle.ohlc_is_valid for candle in fill_candles.values()):
                raise RuntimeError("invalid execution candle")
            close_time = max(point.candle.close_time_utc for point in group)
            processed_time = close_time
            for symbol, point in group_by_symbol.items():
                latest_prices[symbol] = _d(point.candle.close)
                processed_bars[symbol] += 1

            equity, _ = _equity(account.cash_usdc, positions, latest_prices, dust)
            account, daily_paused, _ = _risk_account(account, equity=equity, at=close_time)

            decisions = {}
            for point in group:
                position = positions.get(point.symbol)
                if position is not None and trade_policies_by_symbol:
                    if position.entry_atr <= ZERO:
                        raise RuntimeError(f"missing persisted entry ATR for {point.symbol}")
                    position = replace(
                        position, highest_close=max(position.highest_close, _d(point.candle.close))
                    )
                    positions[point.symbol] = position
                decisions[point.symbol] = policy_gates[point.symbol].decide(
                    point,
                    entry_price=float(position.average_price) if position else None,
                    entry_atr=float(position.entry_atr) if position else 0.0,
                    highest_close=float(position.highest_close) if position else 0.0,
                )

            for point in group:
                decision = decisions[point.symbol]
                signal = decision.signal
                if signal is None or signal.action is not SignalAction.EXIT_LONG:
                    continue
                position = positions[point.symbol]
                rules = rules_by_symbol[point.symbol]
                reference = _d(fill_candles[point.symbol].open)
                fill_price = reference * (ONE - BASELINE_COSTS.adverse_price_rate)
                quantity = _round_down(position.quantity, rules.step_size)
                gross_quote = quantity * fill_price
                if quantity < rules.min_qty or gross_quote < rules.min_notional:
                    emitted.append(_blocked_event(signal, "EXIT_BECAME_DUST"))
                    dust[point.symbol] = dust.get(point.symbol, ZERO) + position.quantity
                    del positions[point.symbol]
                    continue
                fee = gross_quote * BASELINE_COSTS.fee_rate
                net_quote = gross_quote - fee
                account = replace(account, cash_usdc=account.cash_usdc + net_quote)
                realized = net_quote - position.cost_basis_usdc * quantity / position.quantity
                dust[point.symbol] = dust.get(point.symbol, ZERO) + position.quantity - quantity
                emitted.append(
                    PaperEvent(
                        event_id=_event_id(signal),
                        signal_id=signal.signal_id,
                        occurred_at_utc=boundary,
                        symbol=signal.symbol,
                        action=signal.action.value,
                        status=PaperEventStatus.FILLED,
                        reason=decision.exit_reason,
                        reference_price=reference,
                        execution_price=fill_price,
                        base_quantity=quantity,
                        quote_amount_usdc=net_quote,
                        fee_usdc=fee,
                        realized_pnl_usdc=realized,
                        breakout_strength=None,
                        strategy_version=signal.strategy_version,
                    )
                )
                del positions[point.symbol]

            candidates: list[tuple[Signal, IndicatorPoint]] = []
            for point in group:
                decision = decisions[point.symbol]
                signal = decision.signal
                if signal is not None and signal.action is SignalAction.ENTER_LONG:
                    if decision.block_reason:
                        emitted.append(_blocked_event(signal, decision.block_reason))
                        continue
                    candidates.append((signal, point))
            candidates.sort(
                key=lambda item: entry_priority(item[1].rank_strength, item[0].symbol, SYMBOLS)
            )

            for signal, point in candidates:
                if settings.emergency_stop:
                    emitted.append(_blocked_event(signal, "EMERGENCY_STOP"))
                    continue
                if account.halted:
                    emitted.append(_blocked_event(signal, account.halt_reason or "HALTED"))
                    continue
                if daily_paused:
                    emitted.append(_blocked_event(signal, "DAILY_LOSS_5_PERCENT"))
                    continue
                if (
                    sum(position.slot_count for position in positions.values())
                    >= settings.slot_count
                ):
                    emitted.append(_blocked_event(signal, "NO_FREE_SLOT"))
                    continue
                rules = rules_by_symbol[signal.symbol]
                budget = min(settings.target_notional_usdc, account.cash_usdc)
                reference = _d(fill_candles[signal.symbol].open)
                fill_price = reference * (ONE + BASELINE_COSTS.adverse_price_rate)
                gross_quantity = _round_down(budget / fill_price, rules.step_size)
                quote_spend = gross_quantity * fill_price
                if gross_quantity < rules.min_qty or quote_spend < rules.min_notional:
                    emitted.append(_blocked_event(signal, "BELOW_EXCHANGE_MINIMUM"))
                    continue
                if quote_spend <= ZERO or quote_spend > account.cash_usdc:
                    emitted.append(_blocked_event(signal, "INSUFFICIENT_CASH"))
                    continue
                fee_base = gross_quantity * BASELINE_COSTS.fee_rate
                net_quantity = gross_quantity - fee_base
                fee_quote = fee_base * fill_price
                account = replace(account, cash_usdc=account.cash_usdc - quote_spend)
                position = PaperPosition(
                    symbol=signal.symbol,
                    quantity=net_quantity,
                    average_price=fill_price,
                    cost_basis_usdc=quote_spend,
                    entry_time_utc=boundary,
                    entry_signal_id=signal.signal_id,
                    entry_fee_usdc=fee_quote,
                    updated_at_utc=boundary,
                    strategy_version=signal.strategy_version,
                    slot_count=1,
                    entry_atr=_d(signal.atr) if trade_policies_by_symbol else ZERO,
                    highest_close=fill_price if trade_policies_by_symbol else ZERO,
                )
                positions[signal.symbol] = position
                emitted.append(
                    PaperEvent(
                        event_id=_event_id(signal),
                        signal_id=signal.signal_id,
                        occurred_at_utc=position.entry_time_utc,
                        symbol=signal.symbol,
                        action=signal.action.value,
                        status=PaperEventStatus.FILLED,
                        reason=None,
                        reference_price=reference,
                        execution_price=fill_price,
                        base_quantity=net_quantity,
                        quote_amount_usdc=quote_spend,
                        fee_usdc=fee_quote,
                        realized_pnl_usdc=None,
                        breakout_strength=(
                            _d(point.breakout_strength)
                            if point.breakout_strength is not None
                            else None
                        ),
                        strategy_version=signal.strategy_version,
                    )
                )

            checkpoints.update({point.symbol: point.candle.close_time_utc for point in group})

        if processed_time is not None:
            store.apply_cycle(
                account=account,
                positions=positions,
                events=tuple(emitted),
                checkpoints=checkpoints,
                processed_bars=processed_bars,
                dust=dust,
            )
        return tuple(emitted)


def activate_paper_strategy(
    database_path: str,
    points_by_symbol: Mapping[str, tuple[IndicatorPoint, ...]],
    rules_by_symbol: Mapping[str, ExecutionRules],
    strategy: StrategyDefinition,
    *,
    at: datetime | None = None,
) -> tuple[PaperEvent, ...]:
    """Explicitly cut over paper at latest closed prices without deleting history."""

    if not strategy.paper_approved:
        raise ValueError(f"strategy {strategy.version} is not approved for paper")
    if set(points_by_symbol) != set(SYMBOLS) or set(rules_by_symbol) != set(SYMBOLS):
        raise ValueError("paper strategy activation requires all ten symbols")
    moment = (at or datetime.now(UTC)).astimezone(UTC)
    checkpoints = {symbol: points_by_symbol[symbol][-1].candle.close_time_utc for symbol in SYMBOLS}
    latest_prices = {symbol: _d(points_by_symbol[symbol][-1].candle.close) for symbol in SYMBOLS}
    with PaperStore(database_path) as store:
        store.initialize(at=moment)
        previous = store.load_strategy_session()
        if previous.strategy_key == strategy.key and previous.strategy_version == strategy.version:
            return ()
        account = store.load_account()
        positions = store.load_positions()
        events: list[PaperEvent] = []
        cash = account.cash_usdc
        dust = store.load_dust()
        for position in positions:
            rule = rules_by_symbol[position.symbol]
            reference = latest_prices[position.symbol]
            fill_price = reference * (ONE - BASELINE_COSTS.adverse_price_rate)
            quantity = _round_down(position.quantity, rule.step_size)
            gross_quote = quantity * fill_price
            if quantity < rule.min_qty or gross_quote < rule.min_notional:
                raise RuntimeError(
                    f"cannot activate strategy while {position.symbol} is exchange dust"
                )
            fee = gross_quote * BASELINE_COSTS.fee_rate
            net_quote = gross_quote - fee
            realized = net_quote - position.cost_basis_usdc * quantity / position.quantity
            dust[position.symbol] = dust.get(position.symbol, ZERO) + position.quantity - quantity
            signal_id = hashlib.sha256(
                (
                    f"PAPER_STRATEGY_SWITCH|{previous.strategy_version}|"
                    f"{strategy.version}|{position.symbol}|{moment.isoformat()}"
                ).encode()
            ).hexdigest()
            events.append(
                PaperEvent(
                    event_id=hashlib.sha256(f"PAPER|{signal_id}".encode()).hexdigest(),
                    signal_id=signal_id,
                    occurred_at_utc=moment,
                    symbol=position.symbol,
                    action="EXIT_LONG",
                    status=PaperEventStatus.FILLED,
                    reason=f"STRATEGY_SWITCH_TO_{strategy.version}",
                    reference_price=reference,
                    execution_price=fill_price,
                    base_quantity=quantity,
                    quote_amount_usdc=net_quote,
                    fee_usdc=fee,
                    realized_pnl_usdc=realized,
                    breakout_strength=None,
                    strategy_version=position.strategy_version,
                )
            )
            cash += net_quote
        session_equity, _ = _equity(cash, {}, latest_prices, dust)
        activated_account = replace(
            account,
            cash_usdc=cash,
            high_water_equity_usdc=cash,
            day_start_equity_usdc=cash,
            day_start_date_utc=moment.date().isoformat(),
            halted=False,
            halt_reason=None,
            updated_at_utc=moment,
        )
        if strategy.key == "v6":
            # A new research session must not erase an account-wide risk halt or high-water mark.
            activated_account, _, _ = _risk_account(
                replace(account, cash_usdc=cash), equity=session_equity, at=moment
            )
        store.apply_strategy_activation(
            account=activated_account,
            events=tuple(events),
            checkpoints=checkpoints,
            strategy_key=strategy.key,
            strategy_version=strategy.version,
            starting_equity_usdc=session_equity,
            at=moment,
            dust=dust,
        )
    return tuple(events)


def load_paper_portfolio(
    database_path: str,
    latest_prices: Mapping[str, Decimal],
    *,
    at: datetime | None = None,
    strategy_key: str = "v1",
    strategy_version: str = HIXTON_SPEC_VERSION,
    starting_cash_usdc: Decimal | None = None,
) -> PaperPortfolio:
    moment = (at or datetime.now(UTC)).astimezone(UTC)
    with PaperStore(database_path) as store:
        store.initialize(
            at=moment,
            strategy_key=strategy_key,
            strategy_version=strategy_version,
            starting_cash_usdc=starting_cash_usdc,
        )
        store.require_strategy(strategy_key, strategy_version)
        account = store.load_account()
        settings = store.load_settings()
        positions = store.load_positions()
        dust = store.load_dust()
    by_symbol = {position.symbol: position for position in positions}
    equity, unrealized = _equity(account.cash_usdc, by_symbol, latest_prices, dust)
    account, daily_paused, drawdown_pct = _risk_account(account, equity=equity, at=moment)
    return PaperPortfolio(
        account=account,
        settings=settings,
        positions=positions,
        equity_usdc=equity,
        unrealized_pnl_usdc=unrealized,
        daily_loss_paused=daily_paused,
        drawdown_pct=drawdown_pct,
    )

"""Independent 250-USDC coin accounts using the current shared trading engine.

The entry restriction removes competing purchases, never market context or risk
rules. These independent accounts cannot reproduce shared-portfolio trades.
"""

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from hixton.backtest.engine import _buy_and_hold
from hixton.backtest.metrics import drawdown
from hixton.backtest.models import (
    ZERO,
    BacktestResult,
    BatchResult,
    CostModel,
    EquityPoint,
    ExecutionRules,
)
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.models import Candle, SignalAction
from hixton.domain.versions import StrategyDefinition
from hixton.paper.models import PaperSettings

ISOLATED_STARTING_USDC = Decimal("250.00")
DIAGNOSTIC_MODEL = "SHARED_ENGINE_SINGLE_ENTRY_SYMBOL"


def run_coin_diagnostic(
    *,
    symbol: str,
    candles_by_symbol: dict[str, list[Candle]],
    execution_rules: dict[str, ExecutionRules],
    strategy: StrategyDefinition,
    settings: PaperSettings,
    report_start_utc: datetime,
    report_end_utc: datetime,
    costs: CostModel,
) -> BacktestResult:
    if symbol not in strategy.symbols:
        raise ValueError("Diagnostic requires an active strategy symbol")
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles_by_symbol,
        execution_rules=execution_rules,
        strategy=strategy,
        starting_cash=ISOLATED_STARTING_USDC,
        target_notional=ISOLATED_STARTING_USDC / settings.slot_count,
        slot_count=settings.slot_count,
        report_start_utc=report_start_utc,
        report_end_utc=report_end_utc,
        costs=costs,
        reinvest_profits=settings.auto_budget_enabled,
        autonomous_spot=settings.autonomous_performance_enabled,
        allowed_entry_symbols=frozenset({symbol}),
    )
    signals = tuple(s for s in result.signals if s.symbol == symbol)
    signal_ids = {s.signal_id for s in signals}
    assert all(f.signal_id in signal_ids for f in result.fills)
    assert all(t.symbol == symbol for t in result.trades)
    pending = next((s for s in result.pending_signals_at_end if s.symbol == symbol), None)
    dust = result.dust_quantity_by_symbol[symbol]
    quantity = (
        sum(
            (
                f.base_quantity if f.action is SignalAction.ENTER_LONG else -f.base_quantity
                for f in result.fills
            ),
            ZERO,
        )
        - dust
    )
    in_window = [
        c for c in candles_by_symbol[symbol] if report_start_utc <= c.open_time_utc < report_end_utc
    ]
    hold = _buy_and_hold(in_window, ISOLATED_STARTING_USDC, costs)
    metrics = replace(
        result.metrics,
        buy_and_hold_ending_equity=hold,
        buy_and_hold_return_pct=(hold / ISOLATED_STARTING_USDC - 1) * 100,
    )
    return BacktestResult(
        symbol=symbol,
        report_start_utc=result.report_start_utc,
        report_end_utc=result.report_end_utc,
        warmup_start_utc=result.warmup_start_utc,
        cost_model=costs,
        starting_cash=ISOLATED_STARTING_USDC,
        target_notional=result.target_notional,
        signals=signals,
        fills=result.fills,
        trades=result.trades,
        equity_curve=result.equity_curve,
        blocked_signals=tuple(
            b for b in result.blocked_signals if b.split(":", 1)[0] in signal_ids
        ),
        pending_signal_at_end=pending,
        open_position_at_end=symbol in result.open_symbols_at_end,
        open_position_quantity=quantity if symbol in result.open_symbols_at_end else ZERO,
        dust_quantity=dust,
        metrics=metrics,
        data_snapshot_sha256=result.data_snapshot_sha256_by_symbol[symbol],
    )


def combine_coin_diagnostics(results: tuple[BacktestResult, ...]) -> BatchResult:
    starting = sum((r.metrics.starting_equity for r in results), ZERO)
    ending = sum((r.metrics.ending_equity for r in results), ZERO)
    combined = tuple(
        EquityPoint(points[0].time_utc, ZERO, ZERO, sum((p.equity for p in points), ZERO), False)
        for points in zip(*(r.equity_curve for r in results), strict=True)
    )
    absolute, percent = drawdown(combined)
    return BatchResult(
        results=results,
        starting_equity=starting,
        ending_equity=ending,
        net_pnl=ending - starting,
        return_pct=(ending / starting - 1) * 100,
        completed_trades=sum(r.metrics.completed_trades for r in results),
        max_drawdown=absolute,
        max_drawdown_pct=percent,
    )

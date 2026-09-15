"""USDC migration evidence, not a runtime switch or an order dispatcher."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from uuid import uuid4

from hixton.backtest.engine import run_isolated_batch
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import RunResult, _primitive, write_report_bundle
from hixton.constants import TIMEFRAME_DELTA
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.data.storage import CandleStore
from hixton.domain.models import Candle
from hixton.domain.versions import V6_COIN_STRATEGY, V7_USDC_STRATEGY, StrategyDefinition


def continuous_window(
    candles_by_symbol: Mapping[str, list[Candle]],
    requested_start: datetime,
    end: datetime,
    *,
    warmup_bars: int = 400,
) -> tuple[datetime, dict[str, object]]:
    """Choose the common continuous suffix solely by data availability, never PnL.

    Preserve and report every excluded gap; never interpolate or substitute USDC.
    Missing latest bars, duplicates, invalid prices or ordering errors fail closed.
    """
    if tuple(candles_by_symbol) != V7_USDC_STRATEGY.symbols:
        raise ValueError("USDC review requires all ten ordered USDC markets")
    if requested_start.tzinfo is None or end.tzinfo is None or requested_start >= end:
        raise ValueError("Valid timezone-aware review window required")
    if warmup_bars < 1:
        raise ValueError("Positive warm-up required")
    starts = []
    coverage: dict[str, object] = {}
    for symbol, candles in candles_by_symbol.items():
        audit = audit_candles(candles, expected_symbol=symbol)
        if any(issue.code != "GAP" for issue in audit.issues):
            audit.require_valid()
        if not candles or candles[-1].open_time_utc != end - TIMEFRAME_DELTA:
            raise ValueError(f"{symbol}: latest closed bar missing")
        suffix_start = candles[0].open_time_utc
        for previous, current in pairwise(candles):
            if current.open_time_utc != previous.open_time_utc + TIMEFRAME_DELTA:
                suffix_start = current.open_time_utc
        usable = max(requested_start, suffix_start + warmup_bars * TIMEFRAME_DELTA)
        starts.append(usable)
        coverage[symbol] = {
            "downloaded_first_open_utc": candles[0].open_time_utc.isoformat(),
            "continuous_suffix_start_utc": suffix_start.isoformat(),
            "usable_report_start_utc": usable.isoformat(),
            "candle_count": len(candles),
            "gaps": [asdict(issue) for issue in audit.issues],
        }
    start = max(starts)
    if start >= end:
        raise ValueError("Insufficient common USDC history after warm-up")
    return start, coverage


def run_usdc_review(
    project_root: Path,
    end: datetime,
    *,
    code_commit: str,
    usdc_control_database: Path | None = None,
) -> Path:
    """Download/cache real USDC candles, run frozen profiles, retain immutable evidence."""
    if end.tzinfo is None:
        raise ValueError("Review end must be timezone-aware")
    end = end.astimezone(UTC)
    if end.minute or end.second or end.microsecond or end > datetime.now(UTC):
        raise ValueError("Review end must be a past, full UTC hour")
    try:
        requested_start = end.replace(year=end.year - 3)
    except ValueError:
        requested_start = end.replace(year=end.year - 3, day=28)
    warmup_start = requested_start - 400 * TIMEFRAME_DELTA
    strategy = V7_USDC_STRATEGY
    database = project_root / "data" / "usdc-validation.sqlite3"
    client = BinancePublicClient()
    candles_by_symbol: dict[str, list[Candle]] = {}
    rules: dict[str, ExecutionRules] = {}
    market_checks = {}
    # Dedicated cache has no Paper/account/credential tables. Existing USDC DB is untouched.
    for symbol in strategy.symbols:
        rule = client.symbol_rules(symbol)
        if not rule.tradable_for_quote("USDC"):
            raise ValueError(f"{symbol}: USDC spot market not confirmed")
        rules[symbol] = ExecutionRules(
            tick_size=rule.tick_size,
            step_size=rule.step_size,
            min_qty=rule.min_qty,
            min_notional=rule.min_notional,
        )
        market_checks[symbol] = asdict(rule)
        with CandleStore(database) as store:
            cached = store.load_candles(symbol, start=warmup_start, end_exclusive=end)
        # Re-fetch the last two cached bars to catch ordinary recent revisions.
        fetch_start = (
            max(warmup_start, cached[-2].open_time_utc) if len(cached) > 1 else warmup_start
        )
        fetched = client.fetch_klines(symbol, start=fetch_start, end_exclusive=end)
        with CandleStore(database) as store:
            store.put_candles(fetched)
            candles_by_symbol[symbol] = store.load_candles(
                symbol,
                start=warmup_start,
                end_exclusive=end,
            )
        print(f"USDC data: {symbol}, {len(candles_by_symbol[symbol])} closed bars", flush=True)
    start, coverage = continuous_window(candles_by_symbol, requested_start, end)
    output = project_root / "backtests" / "v7" / "runs" / str(uuid4())
    output.mkdir(parents=True, exist_ok=False)
    windows = {"available_common_history": (start, end)}
    if end - start > timedelta(days=365) + 400 * TIMEFRAME_DELTA:
        windows["last_365_days"] = (end - timedelta(days=365), end)
    if end - start > timedelta(days=90) + 400 * TIMEFRAME_DELTA:
        windows["last_90_days"] = (end - timedelta(days=90), end)
    summary: dict[str, object] = {
        "study": "USDC_FROZEN_PROFILE_TRANSFER",
        "quote_asset": "USDC",
        "created_at_utc": datetime.now(UTC),
        "strategy": strategy.config_payload(),
        "code_commit": code_commit,
        "requested_start_utc": requested_start,
        "report_end_utc": end,
        "actual_common_start_utc": start,
        "full_three_years_available": start == requested_start,
        "coverage": coverage,
        "public_market_checks": market_checks,
        "account_tradability_verified": False,
        "live_ready": False,
        "source_file_sha256": {
            path.relative_to(Path(__file__).parents[2]).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(Path(__file__).parents[1].rglob("*.py"))
        },
        "limitations": [
            "Frozen settings transferred from USDC research; not untouched out-of-sample.",
            "Current exchange filters, not point-in-time historical filters.",
            "Baseline/stress are model assumptions, not verified account commissions.",
            "No USDC candles substituted, no gap filling, no account/strategy activation.",
            "Normal live adapter/reconciliation and USDC runtime migration not completed.",
        ],
    }
    outcomes = {}
    for label, (window_start, window_end) in windows.items():
        outcomes[label] = _evaluate_window(
            strategy,
            candles_by_symbol,
            rules,
            window_start,
            window_end,
            output / label,
            code_commit,
        )
        print(f"USDC review: {label} complete", flush=True)
    summary["windows"] = outcomes
    if usdc_control_database is not None:
        control = V6_COIN_STRATEGY
        with CandleStore(usdc_control_database, read_only=True) as store:
            control_candles = {
                symbol: store.load_candles(
                    symbol, start=start - 400 * TIMEFRAME_DELTA, end_exclusive=end
                )
                for symbol in control.symbols
            }
        control_rules = {}
        for symbol in control.symbols:
            rule = client.symbol_rules(symbol)
            if not rule.tradable_for_quote("USDC"):
                raise ValueError(f"{symbol}: control market not confirmed")
            control_rules[symbol] = ExecutionRules(
                tick_size=rule.tick_size,
                step_size=rule.step_size,
                min_qty=rule.min_qty,
                min_notional=rule.min_notional,
            )
        controls = {}
        for label, (window_start, window_end) in windows.items():
            controls[label] = _evaluate_window(
                control,
                control_candles,
                control_rules,
                window_start,
                window_end,
                output / "usdc_same_window_control" / label,
                code_commit,
            )
            print(f"USDC same-window control: {label} complete", flush=True)
        summary["usdc_same_window_control"] = controls
    (output / "summary.json").write_text(
        json.dumps(_primitive(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def _evaluate_window(
    strategy: StrategyDefinition,
    candles: dict[str, list[Candle]],
    rules: dict[str, ExecutionRules],
    start: datetime,
    end: datetime,
    output: Path,
    code_commit: str,
) -> dict[str, object]:
    batch_scenarios = {}
    portfolio_scenarios = {}
    for costs in (BASELINE_COSTS, STRESS_COSTS):
        batch_scenarios[costs.name] = run_isolated_batch(
            candles_by_symbol=candles,
            report_start_utc=start,
            report_end_utc=end,
            costs=costs,
            execution_rules=rules,
            strategy_parameters=strategy.parameters,
            strategy_parameters_by_symbol=strategy.parameter_map(),
            trade_policies_by_symbol=strategy.policy_map(),
            strategy_semantics=strategy.semantics,
            strategy_version=strategy.version,
            symbols=strategy.symbols,
        )
        portfolio_scenarios[costs.name] = run_shared_portfolio_backtest(
            candles_by_symbol=candles,
            report_start_utc=start,
            report_end_utc=end,
            costs=costs,
            execution_rules=rules,
            strategy_parameters=strategy.parameters,
            strategy_parameters_by_symbol=strategy.parameter_map(),
            trade_policies_by_symbol=strategy.policy_map(),
            strategy_semantics=strategy.semantics,
            strategy_version=strategy.version,
            symbols=strategy.symbols,
            starting_cash=Decimal("250"),
            target_notional=Decimal("80"),
            slot_count=3,
            slot_allocation=strategy.slot_allocation,
        )
    for mode, scenarios in (("batch", batch_scenarios), ("portfolio", portfolio_scenarios)):
        report_scenarios: dict[str, RunResult] = dict(scenarios)
        write_report_bundle(
            scenarios=report_scenarios,
            output_root=output / mode,
            config_sha256=hashlib.sha256(
                json.dumps(strategy.config_payload(), sort_keys=True).encode()
            ).hexdigest(),
            code_commit=code_commit,
            report_start_utc=start,
            report_end_utc=end,
            strategy=strategy,
        )
    return {
        "quote_asset": strategy.quote_asset,
        "start_utc": start,
        "end_utc": end,
        "per_coin": {
            scenario: {single.symbol: asdict(single.metrics) for single in batch.results}
            for scenario, batch in batch_scenarios.items()
        },
        "portfolio_3x80": {
            scenario: {
                "metrics": asdict(portfolio.metrics),
                "risk_halted_at_utc": portfolio.risk_halted_at_utc,
                "max_concurrent_positions": portfolio.max_concurrent_positions,
                "open_symbols_at_end": portfolio.open_symbols_at_end,
                "ending_cash": portfolio.equity_curve[-1].cash,
                "ending_position_value": portfolio.equity_curve[-1].position_value,
                "completed_trade_realized_pnl": sum(
                    (trade.realized_pnl for trade in portfolio.trades),
                    Decimal(0),
                ),
            }
            for scenario, portfolio in portfolio_scenarios.items()
        },
    }

"""Immutable JSON/CSV/HTML report bundle writer for single and batch runs."""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import html
import json
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import TypeAlias
from uuid import uuid4

from hixton import __version__
from hixton.backtest.models import BacktestResult, BatchResult, PortfolioBacktestResult
from hixton.constants import TIMEFRAME
from hixton.domain.versions import V1_STRATEGY, StrategyDefinition

RunResult: TypeAlias = BacktestResult | BatchResult | PortfolioBacktestResult


def source_fingerprint(root: Path | None = None) -> str:
    """Include uncommitted Python patches; a Git HEAD alone cannot identify them."""
    root = root or Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for source in sorted(root.rglob("*.py")):
        digest.update(source.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(source.read_text(encoding="utf-8").encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _primitive(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _primitive(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_primitive(item) for item in value]
    return value


def _single_results(result: RunResult) -> tuple[BacktestResult, ...]:
    if isinstance(result, BatchResult):
        return result.results
    if isinstance(result, BacktestResult):
        return (result,)
    return ()


def _metrics_payload(result: RunResult) -> dict[str, object]:
    if isinstance(result, BatchResult):
        return {
            "batch": {
                field.name: _primitive(getattr(result, field.name))
                for field in dataclasses.fields(result)
                if field.name != "results"
            },
            "per_symbol": {
                single.symbol: _primitive(single.metrics) for single in _single_results(result)
            },
        }
    if isinstance(result, PortfolioBacktestResult):
        return {
            "portfolio": {
                "symbols": _primitive(result.symbols),
                "starting_cash": _primitive(result.starting_cash),
                "target_notional": _primitive(result.target_notional),
                "slot_count": result.slot_count,
                "slot_allocation": result.slot_allocation,
                "max_concurrent_positions": result.max_concurrent_positions,
                "risk_limits_applied": result.risk_limits_applied,
                "risk_halted_at_utc": _primitive(result.risk_halted_at_utc),
                "daily_paused_bars": result.daily_paused_bars,
                "open_symbols_at_end": _primitive(result.open_symbols_at_end),
                "signal_count": len(result.signals),
                "fill_count": len(result.fills),
                "blocked_signal_count": len(result.blocked_signals),
                "blocked_reasons": dict(
                    Counter(item.rsplit(":", 1)[-1] for item in result.blocked_signals)
                ),
                "metrics": _primitive(result.metrics),
            }
        }
    return {"per_symbol": {result.symbol: _primitive(result.metrics)}}


def write_report_bundle(
    *,
    scenarios: dict[str, RunResult],
    output_root: Path,
    config_sha256: str,
    code_commit: str,
    report_start_utc: datetime,
    report_end_utc: datetime,
    strategy: StrategyDefinition = V1_STRATEGY,
    python_source_sha256: str | None = None,
) -> Path:
    """Create one new run directory; existing runs are never overwritten."""

    run_modes = {
        "portfolio"
        if isinstance(result, PortfolioBacktestResult)
        else "batch"
        if isinstance(result, BatchResult)
        else "single"
        for result in scenarios.values()
    }
    if len(run_modes) != 1:
        raise ValueError("all cost scenarios must use the same backtest mode")
    run_mode = run_modes.pop()
    run_id = str(uuid4())
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    created_at = datetime.now(UTC)

    data_hashes: dict[str, str] = {}
    for result in scenarios.values():
        if isinstance(result, PortfolioBacktestResult):
            data_hashes.update(result.data_snapshot_sha256_by_symbol)
        for single in _single_results(result):
            data_hashes[single.symbol] = single.data_snapshot_sha256

    metrics_payload = {scenario: _metrics_payload(result) for scenario, result in scenarios.items()}
    (run_directory / "metrics.json").write_text(
        json.dumps(metrics_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_trades(run_directory / "trades.csv", scenarios)
    _write_equity(run_directory / "equity.csv", scenarios)
    _write_html(run_directory / "report.html", run_id, metrics_payload, strategy)

    manifest = {
        "schema_version": 1,
        "quote_asset": strategy.quote_asset,
        "backtest_version": strategy.backtest_version,
        "run_id": run_id,
        "created_at_utc": created_at.isoformat(),
        "status": "VALID",
        "validation_scope": {
            "kind": "HISTORICAL_SIMULATION",
            "application_version": __version__,
            "python_source_sha256": python_source_sha256 or source_fingerprint(),
            "binance_order_execution": "NOT_TESTED_BY_BACKTEST",
            "live_release_granted": False,
            "future_performance_guaranteed": False,
        },
        "run_mode": run_mode,
        "strategy": {
            "version": strategy.version,
            "reference": strategy.reference,
            "semantics": strategy.semantics.value,
            "parameters": None if strategy.coin_profiles else _primitive(strategy.parameters),
            "profiles": strategy.profiles_payload(),
            "paper_approved": strategy.paper_approved,
            "slot_allocation": strategy.slot_allocation,
            "code_commit": code_commit,
            "config_sha256": config_sha256,
        },
        "data": {
            "provider": "binance_spot",
            "timeframe": TIMEFRAME,
            "report_start_utc": report_start_utc.astimezone(UTC).isoformat(),
            "report_end_utc": report_end_utc.astimezone(UTC).isoformat(),
            "snapshot_sha256_by_symbol": data_hashes,
        },
        "scenarios": sorted(scenarios),
        "cost_models": {
            name: _primitive(
                result.results[0].cost_model
                if isinstance(result, BatchResult)
                else result.cost_model
            )
            for name, result in scenarios.items()
        },
        "artifacts": ["metrics.json", "trades.csv", "equity.csv", "report.html"],
        "warning": "Historical results are not a profit guarantee.",
    }
    (run_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_directory


def _write_trades(path: Path, scenarios: dict[str, RunResult]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "scenario",
                "symbol",
                "entry_time_utc",
                "exit_time_utc",
                "entry_signal_id",
                "exit_signal_id",
                "entry_quote_spend",
                "exit_quote_receive",
                "realized_pnl",
                "realized_return_pct",
                "holding_hours",
                "residual_dust_quantity",
            )
        )
        for scenario, result in scenarios.items():
            if isinstance(result, PortfolioBacktestResult):
                result_trades = result.trades
            else:
                result_trades = tuple(
                    trade for single in _single_results(result) for trade in single.trades
                )
            for trade in result_trades:
                writer.writerow(
                    (
                        scenario,
                        trade.symbol,
                        trade.entry_time_utc.isoformat(),
                        trade.exit_time_utc.isoformat(),
                        trade.entry_signal_id,
                        trade.exit_signal_id,
                        trade.entry_quote_spend,
                        trade.exit_quote_receive,
                        trade.realized_pnl,
                        trade.realized_return_pct,
                        trade.holding_hours,
                        trade.residual_dust_quantity,
                    )
                )


def _write_equity(path: Path, scenarios: dict[str, RunResult]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("scenario", "symbol", "time_utc", "cash", "position_value", "equity"))
        for scenario, result in scenarios.items():
            if isinstance(result, PortfolioBacktestResult):
                for point in result.equity_curve:
                    writer.writerow(
                        (
                            scenario,
                            "PORTFOLIO",
                            point.time_utc.isoformat(),
                            point.cash,
                            point.position_value,
                            point.equity,
                        )
                    )
                continue
            for single in _single_results(result):
                for point in single.equity_curve:
                    writer.writerow(
                        (
                            scenario,
                            single.symbol,
                            point.time_utc.isoformat(),
                            point.cash,
                            point.position_value,
                            point.equity,
                        )
                    )


def _write_html(
    path: Path,
    run_id: str,
    metrics_payload: object,
    strategy: StrategyDefinition,
) -> None:
    payload = html.escape(json.dumps(metrics_payload, ensure_ascii=False, indent=2))
    document = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hixton Backtest {html.escape(run_id)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; }}
    pre {{ white-space: pre-wrap; background: #f3f5f8; padding: 1rem; border-radius: .5rem; }}
    .warning {{ border-left: .3rem solid #b26a00; padding-left: 1rem; }}
  </style>
</head>
<body>
  <h1>Hixton Backtest {html.escape(strategy.backtest_version.upper())}</h1>
  <p>Strategie: <code>{html.escape(strategy.version)}</code></p>
  <p>Run-ID: <code>{html.escape(run_id)}</code></p>
  <p class="warning">Historische Simulation der angegebenen Regeln und Einstellungen.
  VALID bedeutet ein gültiges Rechenergebnis, keine Binance-Ausführungsabnahme oder Livefreigabe.
  Historische Ergebnisse sind keine Gewinngarantie.</p>
  <h2>Kennzahlen</h2>
  <pre>{payload}</pre>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")

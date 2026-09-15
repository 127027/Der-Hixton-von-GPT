"""Bounded V8 research using the ordinary engines; never activates a profile."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from hixton.backtest.engine import candle_snapshot_sha256, run_single_backtest
from hixton.backtest.models import (
    BASELINE_COSTS,
    STRESS_COSTS,
    BacktestMetrics,
    ExecutionRules,
)
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint
from hixton.backtest.usdc_review import continuous_window
from hixton.data.storage import CandleStore
from hixton.domain.models import StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V6_COIN_STRATEGY

WEAK_COINS = ("DOTUSDC", "AVAXUSDC", "BNBUSDC")
TRAIN_SPLIT = datetime(2025, 1, 1, tzinfo=UTC)
VALIDATION_START = datetime(2025, 9, 1, tzinfo=UTC)
D = Decimal


@dataclass(frozen=True)
class Candidate:
    name: str
    parameters: StrategyParameters
    policy: TradePolicy


def candidates(symbol: str) -> tuple[Candidate, ...]:
    """Predeclared six variants; no expansion after viewing validation results."""
    if symbol not in WEAK_COINS:
        raise ValueError("V8 changes only DOT, AVAX and BNB")
    base = V6_COIN_STRATEGY.parameters_for(symbol)
    policy = V6_COIN_STRATEGY.policy_for(symbol)
    narrow = replace(base, band_multiplier=round(base.band_multiplier - 0.6, 1))
    return (
        Candidate("current", base, policy),
        Candidate("narrow", narrow, policy),
        Candidate("stop4", base, replace(policy, stop_atr=4)),
        Candidate("trail6", base, replace(policy, trail_atr=6)),
        Candidate("narrow_stop4", narrow, replace(policy, stop_atr=4)),
        Candidate("narrow_trail6", narrow, replace(policy, trail_atr=6)),
    )


def select_training(rows: dict[str, tuple[BacktestMetrics, ...]]) -> str:
    """Selection sees training only. Failed eligibility falls back to current."""
    reference = rows["current"]
    eligible = []
    for name, metrics in rows.items():
        if name == "current":
            continue
        if len(metrics) != len(reference):
            raise ValueError("training windows do not match")
        if any(
            m.completed_trades < 5 or m.max_drawdown_pct > r.max_drawdown_pct + D(2)
            for m, r in zip(metrics, reference, strict=True)
        ):
            continue
        if sum(m.completed_trades for m in metrics) < sum(r.completed_trades for r in reference):
            continue
        if sum(m.net_pnl for m in metrics) < sum(r.net_pnl for r in reference):
            continue
        eligible.append(name)
    return max(
        eligible,
        key=lambda name: (
            min(m.return_pct for m in rows[name]),
            sum(m.net_pnl for m in rows[name]),
            sum(m.completed_trades for m in rows[name]),
            name,
        ),
        default="current",
    )


def acceptance(reference: BacktestMetrics, trial: BacktestMetrics) -> bool:
    """Positive net result, no lower return/trade count, at most +2 pp drawdown."""
    return (
        trial.net_pnl > 0
        and trial.ending_equity >= reference.ending_equity
        and trial.max_drawdown_pct <= reference.max_drawdown_pct + D(2)
        and trial.completed_trades >= reference.completed_trades
    )


def _save(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def run_weak_coin_review(database: Path, output: Path, end: datetime) -> None:
    """Read one SQLite snapshot, compare frozen candidates, leave all accounts alone."""
    if end.tzinfo is None or end.minute or end.second or end.microsecond:
        raise ValueError("end must be an aware full hour")
    end = end.astimezone(UTC)
    if end <= VALIDATION_START + timedelta(days=90):
        raise ValueError("at least 90 days of validation required")
    definition = V6_COIN_STRATEGY
    requested = datetime(2023, 9, 14, 13, tzinfo=UTC)
    with CandleStore(database, read_only=True) as store:
        # A single WAL-aware transaction prevents mixing snapshots across coins.
        store._connection.execute("BEGIN")
        candles = {
            symbol: store.load_candles(
                symbol, start=requested - timedelta(hours=400), end_exclusive=end
            )
            for symbol in definition.symbols
        }
        rules = {}
        for symbol in definition.symbols:
            saved = store.load_symbol_rules(symbol)
            if saved is None or saved.status != "TRADING" or not saved.spot_allowed:
                raise ValueError(f"missing or invalid stored Binance rules: {symbol}")
            if "MARKET" not in saved.order_types or saved.quote_asset != "USDC":
                raise ValueError(f"USDC market orders unavailable: {symbol}")
            rules[symbol] = ExecutionRules(
                saved.tick_size, saved.step_size, saved.min_qty, saved.min_notional
            )
    start, coverage = continuous_window(candles, requested, end)
    if start >= TRAIN_SPLIT - timedelta(days=90):
        raise ValueError("insufficient first training window")
    windows = {
        "train_a": (start, TRAIN_SPLIT),
        "train_b": (TRAIN_SPLIT, VALIDATION_START),
        "validation": (VALIDATION_START, end),
        "full": (start, end),
    }
    catalog = {symbol: candidates(symbol) for symbol in WEAK_COINS}
    manifest = {
        "study": "v8-weak-coins-1",
        "active_reference": definition.config_payload(),
        "python_source_sha256": source_fingerprint(),
        "windows": windows,
        "coverage": coverage,
        "data_sha256": {s: candle_snapshot_sha256(c) for s, c in candles.items()},
        "execution_rules": {s: asdict(r) for s, r in rules.items()},
        "costs": [asdict(BASELINE_COSTS), asdict(STRESS_COSTS)],
        "candidates": {s: [asdict(c) for c in cs] for s, cs in catalog.items()},
        "selection": "Stress training only; >=5 trades/window; DD <= current+2pp; "
        "aggregate trades and net PnL >= current; maximize worst-window return.",
        "acceptance": "Both costs in validation and full: positive net PnL, "
        "return and trade count >= current; DD <= current+2pp. "
        "Combined portfolio must additionally remain unhalted in both windows/costs.",
        "limitations": "Previously inspected history, NOT untouched holdout. "
        "Current exchange filters, not point-in-time filters. No real execution proof. "
        "Research only; no automatic activation; risk limits remain enabled.",
    }
    output.mkdir(parents=True, exist_ok=False)
    _save(output / "manifest.json", manifest)  # Persist plan before testing candidates.
    research_id = (
        "HIXTON-V6-WEAK-RESEARCH-"
        + hashlib.sha256(
            json.dumps(manifest["candidates"], sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
    )
    cache: dict[tuple[str, str, str, str], BacktestMetrics] = {}

    def single(symbol: str, candidate: Candidate, window: str, cost_name: str) -> BacktestMetrics:
        key = (symbol, candidate.name, window, cost_name)
        if key not in cache:
            low, high = windows[window]
            result = run_single_backtest(
                symbol=symbol,
                candles=candles[symbol],
                report_start_utc=low,
                report_end_utc=high,
                starting_cash=D(250),
                target_notional=D(250),
                costs=BASELINE_COSTS if cost_name == "baseline" else STRESS_COSTS,
                execution_rules=rules[symbol],
                strategy_parameters=candidate.parameters,
                strategy_semantics=definition.semantics,
                strategy_version=research_id,
                trade_policy=candidate.policy,
            )
            cache[key] = result.metrics
            print(
                f"{symbol} {candidate.name} {window} {cost_name}: "
                f"end={result.metrics.ending_equity:.2f}, "
                f"trades={result.metrics.completed_trades}",
                flush=True,
            )
        return cache[key]

    selected = {}
    for symbol, variants in catalog.items():
        training = {
            c.name: tuple(single(symbol, c, w, "stress") for w in ("train_a", "train_b"))
            for c in variants
        }
        selected[symbol] = next(c for c in variants if c.name == select_training(training))
    _save(output / "training_selection.json", {s: asdict(c) for s, c in selected.items()})
    print("Training selection frozen; evaluating validation and full window", flush=True)
    coin_pass = {}
    for symbol in definition.symbols:
        current = Candidate(
            "current", definition.parameters_for(symbol), definition.policy_for(symbol)
        )
        flags = []
        for window in ("validation", "full"):
            for cost_name in ("baseline", "stress"):
                ref = single(symbol, current, window, cost_name)
                if symbol in selected:
                    flags.append(
                        acceptance(ref, single(symbol, selected[symbol], window, cost_name))
                    )
        if symbol in selected:
            coin_pass[symbol] = selected[symbol].name != "current" and all(flags)

    portfolios: dict[str, dict[str, object]] = {}
    portfolio_metrics = {}
    for window in ("validation", "full"):
        for cost in (BASELINE_COSTS, STRESS_COSTS):
            for label in ("current", "training_selected"):
                parameters = {s: definition.parameters_for(s) for s in definition.symbols}
                policies = {s: definition.policy_for(s) for s in definition.symbols}
                if label == "training_selected":
                    parameters.update({s: c.parameters for s, c in selected.items()})
                    policies.update({s: c.policy for s, c in selected.items()})
                low, high = windows[window]
                result = run_shared_portfolio_backtest(
                    candles_by_symbol=candles,
                    report_start_utc=low,
                    report_end_utc=high,
                    starting_cash=D(250),
                    target_notional=D(80),
                    slot_count=3,
                    costs=cost,
                    execution_rules=rules,
                    strategy_parameters=definition.parameters,
                    strategy_parameters_by_symbol=parameters,
                    trade_policies_by_symbol=policies,
                    strategy_semantics=definition.semantics,
                    strategy_version=research_id,
                    slot_allocation=definition.slot_allocation,
                    apply_risk_limits=True,
                    symbols=definition.symbols,
                )
                key = f"{window}/{cost.name}/{label}"
                portfolio_metrics[key] = result.metrics
                portfolios[key] = {
                    "metrics": asdict(result.metrics),
                    "risk_halted_at_utc": result.risk_halted_at_utc,
                }
                print(
                    f"Portfolio {key}: {result.metrics.ending_equity:.2f}, "
                    f"trades={result.metrics.completed_trades}, "
                    f"halt={result.risk_halted_at_utc}",
                    flush=True,
                )
    portfolio_pass = all(
        acceptance(
            portfolio_metrics[f"{w}/{c}/current"], portfolio_metrics[f"{w}/{c}/training_selected"]
        )
        and portfolios[f"{w}/{c}/training_selected"]["risk_halted_at_utc"] is None
        for w in ("validation", "full")
        for c in ("baseline", "stress")
    )
    _save(
        output / "summary.json",
        {
            "manifest": manifest,
            "research_id": research_id,
            "selected": {s: asdict(c) for s, c in selected.items()},
            "coin_acceptance": coin_pass,
            "combined_portfolio_acceptance": portfolio_pass,
            "research_gate_passed": all(coin_pass.values()) and portfolio_pass,
            "activation_performed": False,
            "singles": {"/".join(k): asdict(m) for k, m in cache.items()},
            "portfolios": portfolios,
        },
    )
    print(f"Complete: {output / 'summary.json'}; active Paper/Live unchanged", flush=True)

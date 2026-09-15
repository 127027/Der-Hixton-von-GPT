"""V9 portfolio-first policy study. No activation, account writes or live orders."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from hixton.backtest.engine import candle_snapshot_sha256, run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint
from hixton.backtest.usdc_review import continuous_window
from hixton.data.storage import CandleStore
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V6_COIN_STRATEGY

D = Decimal


def policy_catalog() -> dict[str, dict[str, TradePolicy]]:
    """Freeze ten hypotheses before inspection; never optimize on validation."""
    variations: dict[str, dict[str, float]] = {
        "current": {},
        "cmo20": {"cmo_floor": 0.2},
        "slope24": {"slope_bars": 24},
        "slope72": {"slope_bars": 72},
        "stop2": {"stop_atr": 2},
        "stop4": {"stop_atr": 4},
        "trail4": {"trail_atr": 4},
        "cmo20_stop2": {"cmo_floor": 0.2, "stop_atr": 2},
        "slope24_stop2": {"slope_bars": 24, "stop_atr": 2},
        "slope24_trail4": {"slope_bars": 24, "trail_atr": 4},
    }
    result = {}
    for name, overrides in variations.items():
        policies = {}
        for symbol in V6_COIN_STRATEGY.symbols:
            base = V6_COIN_STRATEGY.policy_for(symbol)
            changes = dict(overrides)
            # Preserve stronger pre-existing entry filters. Stop variants explicitly
            # replace the per-position ATR stop; no portfolio limit is changed.
            for field in ("cmo_floor", "slope_bars"):
                if field in changes:
                    changes[field] = max(changes[field], getattr(base, field))
            policies[symbol] = replace(
                base,
                cmo_floor=changes.get("cmo_floor", base.cmo_floor),
                slope_bars=int(changes.get("slope_bars", base.slope_bars)),
                stop_atr=changes.get("stop_atr", base.stop_atr),
                trail_atr=changes.get("trail_atr", base.trail_atr),
            )
        result[name] = policies
    return result


def training_choice(scores: dict[str, tuple[Decimal, Decimal]]) -> str:
    """Return best worst-window return; current wins exact ties."""
    return max(
        scores, key=lambda name: (min(scores[name]), sum(scores[name]), name == "current", name)
    )


def run_portfolio_review(database: Path, output: Path, end: datetime) -> None:
    if end.tzinfo is None or end.minute or end.second or end.microsecond:
        raise ValueError("end must be an aware full hour")
    end = end.astimezone(UTC)
    validation = datetime(2025, 9, 1, tzinfo=UTC)
    if end <= validation + timedelta(days=90):
        raise ValueError("insufficient validation")
    requested = datetime(2023, 9, 15, tzinfo=UTC)
    definition = V6_COIN_STRATEGY
    with CandleStore(database, read_only=True) as store:
        store._connection.execute("BEGIN")
        candles = {
            s: store.load_candles(s, start=requested - timedelta(hours=400), end_exclusive=end)
            for s in definition.symbols
        }
        rules = {}
        for s in definition.symbols:
            saved = store.load_symbol_rules(s)
            if saved is None or saved.status != "TRADING" or not saved.spot_allowed:
                raise ValueError(f"unavailable market {s}")
            if saved.quote_asset != "USDC" or "MARKET" not in saved.order_types:
                raise ValueError(f"unavailable USDC MARKET {s}")
            rules[s] = ExecutionRules(
                saved.tick_size, saved.step_size, saved.min_qty, saved.min_notional
            )
    start, coverage = continuous_window(candles, requested, end)
    split = datetime(2025, 1, 1, tzinfo=UTC)
    if start >= split - timedelta(days=90):
        raise ValueError("insufficient training")
    windows = {
        "train_a": (start, split),
        "train_b": (split, validation),
        "validation": (validation, end),
        "full": (start, end),
    }
    catalog = policy_catalog()
    output.mkdir(parents=True, exist_ok=False)

    def save(name: str, value: object) -> None:
        (output / name).write_text(
            json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8"
        )

    manifest = {
        "study": "v9-portfolio-first-1",
        "source_hash": source_fingerprint(),
        "active_strategy": definition.config_payload(),
        "windows": windows,
        "coverage": coverage,
        "data_hashes": {s: candle_snapshot_sha256(c) for s, c in candles.items()},
        "rules": {s: asdict(r) for s, r in rules.items()},
        "costs": [asdict(BASELINE_COSTS), asdict(STRESS_COSTS)],
        "candidates": {n: {s: asdict(p) for s, p in ps.items()} for n, ps in catalog.items()},
        "selection": "Train A/B stress only; maximize worst return, then sum; current wins ties.",
        "gate": "Finalist positive and unhalted in both full/validation and baseline/stress; "
        "return >= reference; DD <= reference+2pp. No automatic activation.",
        "limitations": "Previously inspected data, NOT untouched holdout. Historical filters not "
        "available. Same 3x80 portfolio and fixed risk. No future-profit guarantee.",
    }
    save("manifest.json", manifest)
    digest = hashlib.sha256(
        json.dumps(manifest["candidates"], sort_keys=True).encode()
    ).hexdigest()[:12]
    research_id = f"HIXTON-V6-V9-RESEARCH-{digest}"
    portfolios: dict[str, dict] = {}

    def portfolio(name: str, window: str, stress: bool) -> dict:
        costs = STRESS_COSTS if stress else BASELINE_COSTS
        key = f"{name}/{window}/{costs.name}"
        if key not in portfolios:
            low, high = windows[window]
            r = run_shared_portfolio_backtest(
                candles_by_symbol=candles,
                report_start_utc=low,
                report_end_utc=high,
                starting_cash=D(250),
                target_notional=D(80),
                slot_count=3,
                costs=costs,
                execution_rules=rules,
                strategy_parameters_by_symbol=definition.parameter_map(),
                trade_policies_by_symbol=catalog[name],
                strategy_semantics=definition.semantics,
                strategy_version=research_id,
                slot_allocation=definition.slot_allocation,
                apply_risk_limits=True,
            )
            portfolios[key] = {"metrics": asdict(r.metrics), "halt": r.risk_halted_at_utc}
            print(
                f"{key}: {r.metrics.ending_equity:.2f}; trades={len(r.trades)}; "
                f"halt={r.risk_halted_at_utc}",
                flush=True,
            )
            save("portfolios.json", portfolios)
        return portfolios[key]

    scores = {
        n: (
            portfolio(n, "train_a", True)["metrics"]["return_pct"],
            portfolio(n, "train_b", True)["metrics"]["return_pct"],
        )
        for n in catalog
    }
    selected = training_choice(scores)
    save("selection.json", {"selected": selected, "training_scores": scores})
    print(f"Frozen training choice: {selected}; now validation, no reselection", flush=True)
    passed = selected != "current"
    for window in ("validation", "full"):
        for stress in (False, True):
            ref = portfolio("current", window, stress)
            trial = portfolio(selected, window, stress)
            m, b = trial["metrics"], ref["metrics"]
            passed = (
                passed
                and trial["halt"] is None
                and m["net_pnl"] > 0
                and (
                    m["return_pct"] >= b["return_pct"]
                    and m["max_drawdown_pct"] <= b["max_drawdown_pct"] + D(2)
                )
            )
    # Diagnose each coin of the one selected portfolio, never select ten winners
    # independently after seeing holdout or replace this losing finalist.
    singles = {}
    for s in definition.symbols:
        for name in dict.fromkeys(("current", selected)):
            for window in ("full", "validation"):
                for costs in (BASELINE_COSTS, STRESS_COSTS):
                    low, high = windows[window]
                    r = run_single_backtest(
                        symbol=s,
                        candles=candles[s],
                        report_start_utc=low,
                        report_end_utc=high,
                        starting_cash=D(250),
                        target_notional=D(250),
                        costs=costs,
                        execution_rules=rules[s],
                        strategy_parameters=definition.parameters_for(s),
                        trade_policy=catalog[name][s],
                        strategy_semantics=definition.semantics,
                        strategy_version=research_id,
                    )
                    singles[f"{s}/{name}/{window}/{costs.name}"] = asdict(r.metrics)
        print(f"Coin diagnosis complete: {s}", flush=True)
    save(
        "summary.json",
        {
            "manifest": manifest,
            "selected": selected,
            "portfolio_gate_passed": passed,
            "activation_performed": False,
            "portfolios": portfolios,
            "singles": singles,
        },
    )
    print(f"Complete; gate={passed}; active strategy unchanged: {output}", flush=True)

"""Bounded, chronological research; never changes the running strategy or ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path

from hixton.backtest.engine import candle_snapshot_sha256, run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.constants import SYMBOLS
from hixton.data.quality import audit_candles
from hixton.data.storage import CandleStore
from hixton.domain.models import IndicatorPoint, StrategyParameters, StrategySemantics
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V2_RESEARCH_STRATEGY


def screen(
    points: list[IndicatorPoint],
    start: datetime,
    end: datetime,
    bps: float,
    *,
    scale_in: bool = False,
    budget: float = 250.0,
    slots: int = 1,
) -> dict[str, float | int]:
    """Causal next-open screening; exact Decimal finalists are checked separately."""
    if start >= end or budget <= 0 or slots <= 0 or bps < 10:
        raise ValueError("invalid screening window, capital or costs")
    cash, quantity, pending, used = budget * slots, 0.0, 0, 0
    equity = cash
    peak, drawdown, completed, entries = cash, 0.0, 0, 0
    last_entry_price, last_entry_index = 0.0, -1000
    adverse = bps / 10000 - 0.001
    previous: IndicatorPoint | None = None
    for point in points:
        if not start <= point.candle.open_time_utc < end:
            previous = point
            continue
        if pending == 1:
            spend = min(budget, cash)
            if spend >= 5:
                last_entry_price = point.candle.open * (1 + adverse)
                quantity += spend / last_entry_price * 0.999
                cash -= spend
                used += 1
                entries += 1
                last_entry_index = point.index
        elif pending == -1 and quantity:
            cash += quantity * point.candle.open * (1 - adverse) * 0.999
            quantity, used = 0.0, 0
            completed += 1
        pending = 0
        if point.tradable:
            if point.flip_down and quantity:
                pending = -1
            elif (point.flip_up and not quantity) or (
                scale_in
                and quantity
                and used < slots
                and previous is not None
                and point.upper is not None
                and previous.upper is not None
                and point.atr is not None
                and point.candle.close > point.upper
                and previous.candle.close <= previous.upper
                and point.index - last_entry_index >= 24
                and point.candle.close >= last_entry_price + point.atr
            ):
                pending = 1
        equity = cash + quantity * point.candle.close
        peak = max(peak, equity)
        drawdown = max(drawdown, 100 * (1 - equity / peak))
        previous = point
    return {
        "ending_equity": equity,
        "return_pct": (equity / (budget * slots) - 1) * 100,
        "max_drawdown_pct": drawdown,
        "completed_trades": completed,
        "entries": entries,
    }


def run_review(database: Path, output: Path) -> None:
    """Freeze training selection before examining the third year of each coin."""
    if output.exists():
        raise ValueError("research output already exists; choose a new run directory")
    start = datetime(2023, 9, 1, 12, tzinfo=UTC)
    split1, split2, end = (start.replace(year=year) for year in (2024, 2025, 2026))
    grid = [
        StrategyParameters(v, 20, s, a, b, 400)
        for v, s, a, b in product((6, 10), (8, 15), (60, 120), (3.2, 3.8, 4.4))
    ]
    incumbent = V2_RESEARCH_STRATEGY.parameters
    selected: dict[str, StrategyParameters] = {}
    candles_by_symbol = {}
    rules: dict[str, ExecutionRules] = {}
    payload: dict[str, object] = {
        "schema": "HIXTON-RESEARCH-REVIEW-1",
        "incumbent_version": V2_RESEARCH_STRATEGY.version,
        "cost_models": [asdict(BASELINE_COSTS), asdict(STRESS_COSTS)],
        "source_sha256": {
            str(path.relative_to(Path(__file__).parents[1])): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for folder in ("backtest", "domain", "data")
            for path in sorted((Path(__file__).parents[1] / folder).glob("*.py"))
        },
        "status": "RESEARCH_ONLY",
        "selection": "maximize worst training-year stress return, then mean",
        "grid": [asdict(p) for p in grid],
        "candidates_per_coin": len(grid),
        "training": [start.isoformat(), split2.isoformat()],
        "validation": [split2.isoformat(), end.isoformat()],
        "limitations": [
            "Validation year was inspected during V2 research; not an untouched holdout.",
            "Screening omits quantity rounding; finalists use production Decimal engine.",
            "Scale-in is a separate exploratory screen, never paper-approved.",
        ],
    }
    result_coins = {}
    with CandleStore(database) as store:
        for symbol in SYMBOLS:
            candles = store.load_candles(
                symbol, start=start - timedelta(hours=400), end_exclusive=end
            )
            audit_candles(
                candles,
                expected_symbol=symbol,
                expected_start=start - timedelta(hours=400),
                expected_end_exclusive=end,
            ).require_valid()
            candles_by_symbol[symbol] = candles
            rule = store.load_symbol_rules(symbol)
            if rule is None:
                raise ValueError(f"missing rules for {symbol}")
            rules[symbol] = ExecutionRules(
                rule.tick_size, rule.step_size, rule.min_qty, rule.min_notional
            )
    for symbol in SYMBOLS:
        ranked = []
        best_points = None
        best_key = (-float("inf"), -float("inf"))
        for parameters in grid:
            points = list(
                evaluate_batch(
                    symbol,
                    candles_by_symbol[symbol],
                    parameters=parameters,
                    semantics=StrategySemantics.PINE_V6,
                )
            )
            train = [screen(points, lo, hi, 40.0) for lo, hi in ((start, split1), (split1, split2))]
            returns = [float(row["return_pct"]) for row in train]
            key = (min(returns), sum(returns))
            ranked.append({"parameters": asdict(parameters), "training_stress": train})
            if key > best_key:
                best_key, best_points = key, points
                selected[symbol] = parameters
        assert best_points is not None
        exact = {}
        for label, parameters in (("incumbent", incumbent), ("selected", selected[symbol])):
            for window, lo in (("validation", split2), ("full_3y", start)):
                for cost in (BASELINE_COSTS, STRESS_COSTS):
                    result = run_single_backtest(
                        symbol=symbol,
                        candles=candles_by_symbol[symbol],
                        report_start_utc=lo,
                        report_end_utc=end,
                        costs=cost,
                        execution_rules=rules[symbol],
                        strategy_parameters=parameters,
                        strategy_semantics=StrategySemantics.PINE_V6,
                    )
                    exact[f"{label}_{window}_{cost.name}"] = asdict(result.metrics)
        result_coins[symbol] = {
            "selected": asdict(selected[symbol]),
            "training_search": ranked,
            "data_sha256": candle_snapshot_sha256(candles_by_symbol[symbol]),
            "exact": exact,
            "scale_in_validation_screen": {
                policy: screen(best_points, split2, end, 40, scale_in=enabled, budget=80, slots=3)
                for policy, enabled in (("one_slot", False), ("confirmed_additions", True))
            },
        }
        print(
            f"{symbol}: selected {selected[symbol]} validation stress "
            f"{exact['selected_validation_stress']['ending_equity']} "
            f"vs V2 {exact['incumbent_validation_stress']['ending_equity']}",
            flush=True,
        )
    portfolios = {}
    for label, mapping in (("incumbent", None), ("coin_specific", selected)):
        for window, lo in (("validation", split2), ("full_3y", start)):
            for cost in (BASELINE_COSTS, STRESS_COSTS):
                portfolio_result = run_shared_portfolio_backtest(
                    candles_by_symbol=candles_by_symbol,
                    report_start_utc=lo,
                    report_end_utc=end,
                    costs=cost,
                    execution_rules=rules,
                    strategy_parameters=incumbent,
                    strategy_parameters_by_symbol=mapping,
                    strategy_semantics=StrategySemantics.PINE_V6,
                )
                portfolios[f"{label}_{window}_{cost.name}"] = {
                    "metrics": asdict(portfolio_result.metrics),
                    "halt": portfolio_result.risk_halted_at_utc,
                    "blocked": len(portfolio_result.blocked_signals),
                }
    payload.update(
        coins=result_coins,
        portfolios=portfolios,
        execution_rules={symbol: asdict(rule) for symbol, rule in rules.items()},
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Saved {output}", flush=True)

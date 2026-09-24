"""Scaling sanity check for the shared ranked-repeat portfolio.

Research only. Verifies whether a true 4x capital/notional scale of 250/3x80
behaves linearly, and contrasts it with the structurally different 1000/10x100
layout.
"""

from __future__ import annotations

import json
from decimal import Decimal as D
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.allocation import RANKED_REPEAT
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map
from scripts.coin_optimization_cycle import _rules


def _run(
    *,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Any],
    start: Any,
    end: Any,
    starting_cash: D,
    target_notional: D,
    slot_count: int,
    costs: Any,
) -> dict[str, object]:
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=starting_cash,
        target_notional=target_notional,
        slot_count=slot_count,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=V6_COIN_STRATEGY.parameters,
        strategy_parameters_by_symbol={
            symbol: candidate.parameters for symbol, candidate in profiles.items()
        },
        trade_policies_by_symbol={
            symbol: candidate.policy for symbol, candidate in profiles.items()
        },
        strategy_semantics=V6_COIN_STRATEGY.semantics,
        strategy_version="HIXTON-V6-SCALING-SANITY",
        slot_allocation=RANKED_REPEAT,
        apply_risk_limits=True,
        symbols=V6_COIN_STRATEGY.symbols,
    )
    return {
        "starting_cash": str(starting_cash),
        "target_notional": str(target_notional),
        "slot_count": slot_count,
        "max_initial_commitment": str(target_notional * slot_count),
        "ending_equity": str(result.metrics.ending_equity),
        "net_pnl": str(result.metrics.net_pnl),
        "return_pct": str(result.metrics.return_pct),
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "position_cycles": result.metrics.completed_trades,
        "slot_trades": result.metrics.completed_slot_trades,
        "max_concurrent_slots": result.max_concurrent_positions,
        "blocked_no_free_slot": sum(
            1 for item in result.blocked_signals if item.endswith(":NO_FREE_SLOT")
        ),
    }


def main() -> None:
    _, start, end = safe_closed_window()
    rules = _rules()
    profiles = _candidate_map(research=True)
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
    )
    variants = {
        "base_250_3x80": ("250", "80", 3),
        "true_4x_1000_3x320": ("1000", "320", 3),
        "layout_1000_10x100": ("1000", "100", 10),
        "same_tranche_1000_12x80": ("1000", "80", 12),
    }
    output: dict[str, object] = {
        "report_start_utc": start.isoformat(),
        "report_end_utc": end.isoformat(),
        "research_only": True,
        "profiles": "research_candidate",
        "baseline": {},
        "stress": {},
    }
    for cost_label, costs in (("baseline", BASELINE_COSTS), ("stress", STRESS_COSTS)):
        bucket = output[cost_label]
        assert isinstance(bucket, dict)
        for name, (cash, target, slots) in variants.items():
            bucket[name] = _run(
                candles=history.candles_by_symbol,
                rules=rules,
                profiles=profiles,
                start=start,
                end=end,
                starting_cash=D(cash),
                target_notional=D(target),
                slot_count=slots,
                costs=costs,
            )
    baseline = output["baseline"]
    assert isinstance(baseline, dict)
    base = D(str(baseline["base_250_3x80"]["ending_equity"]))
    scaled = D(str(baseline["true_4x_1000_3x320"]["ending_equity"]))
    output["linearity_check"] = {
        "expected_4x_ending_equity": str(base * D("4")),
        "actual_4x_ending_equity": str(scaled),
        "absolute_difference": str(scaled - base * D("4")),
        "ratio_actual_to_expected": str(scaled / (base * D("4"))),
    }
    path = Path("evidence") / "capital-scaling-sanity.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

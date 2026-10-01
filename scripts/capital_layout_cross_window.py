"""Cross-window robustness gate for fixed-250-USDC capital-layout candidates.

Research only. Selects the leading strict frequency candidate from the capital
layout evidence and compares it with the current 2x125 ranked-repeat reference
across three non-overlapping market windows under baseline and stress costs.
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map
from scripts.capital_budget_optimizer import Layout, _run
from scripts.coin_optimization_cycle import _rules

REFERENCE = Layout(RANKED_REPEAT, 2, D("125"))


def _parse_layout(value: str) -> Layout:
    policy, geometry = value.split(":", 1)
    slots_text, tranche_text = geometry.split("x", 1)
    if policy not in {RANKED_REPEAT, ONE_PER_SYMBOL}:
        raise ValueError(f"unsupported allocation policy: {policy}")
    return Layout(policy, int(slots_text), D(tranche_text))


def _window_rows(
    *,
    candidate: Layout,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Any],
    start: Any,
    end: Any,
) -> list[dict[str, object]]:
    cut1 = start + timedelta(days=365)
    cut2 = cut1 + timedelta(days=365)
    windows = ((start, cut1), (cut1, cut2), (cut2, end))
    rows: list[dict[str, object]] = []
    for index, (low, high) in enumerate(windows, start=1):
        if high <= low:
            raise RuntimeError("invalid cross-window boundary")
        ref_base = _run(
            candles=candles,
            rules=rules,
            profiles=profiles,
            start=low,
            end=high,
            layout=REFERENCE,
            costs=BASELINE_COSTS,
        )
        cand_base = _run(
            candles=candles,
            rules=rules,
            profiles=profiles,
            start=low,
            end=high,
            layout=candidate,
            costs=BASELINE_COSTS,
        )
        ref_stress = _run(
            candles=candles,
            rules=rules,
            profiles=profiles,
            start=low,
            end=high,
            layout=REFERENCE,
            costs=STRESS_COSTS,
        )
        cand_stress = _run(
            candles=candles,
            rules=rules,
            profiles=profiles,
            start=low,
            end=high,
            layout=candidate,
            costs=STRESS_COSTS,
        )
        base_delta = D(str(cand_base["ending_equity"])) - D(str(ref_base["ending_equity"]))
        stress_delta = D(str(cand_stress["ending_equity"])) - D(str(ref_stress["ending_equity"]))
        base_dd_delta = D(str(cand_base["max_drawdown_pct"])) - D(
            str(ref_base["max_drawdown_pct"])
        )
        stress_dd_delta = D(str(cand_stress["max_drawdown_pct"])) - D(
            str(ref_stress["max_drawdown_pct"])
        )
        cycle_delta = int(cand_base["position_cycles"]) - int(ref_base["position_cycles"])
        rows.append(
            {
                "window": index,
                "start_utc": low.isoformat(),
                "end_utc": high.isoformat(),
                "baseline_equity_delta_usdc": str(base_delta),
                "stress_equity_delta_usdc": str(stress_delta),
                "position_cycle_delta": cycle_delta,
                "baseline_drawdown_delta_pp": str(base_dd_delta),
                "stress_drawdown_delta_pp": str(stress_dd_delta),
                "positive": base_delta >= 0 and stress_delta >= 0,
            }
        )
    return rows


def evaluate(evidence: dict[str, Any]) -> dict[str, object]:
    comparison = evidence.get("frequency_comparison")
    if not isinstance(comparison, dict):
        raise RuntimeError("frequency comparison missing")
    strict = comparison.get("strict_frequency_improvements")
    if not isinstance(strict, list) or not strict:
        return {
            "schema_version": 1,
            "candidate": None,
            "cross_window_pass": False,
            "reason": "no_strict_frequency_candidate",
        }
    candidate = _parse_layout(str(strict[0]))

    _, start, end = safe_closed_window()
    rules = _rules()
    profiles = _candidate_map(research=False)
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
    )
    rows = _window_rows(
        candidate=candidate,
        candles=history.candles_by_symbol,
        rules=rules,
        profiles=profiles,
        start=start,
        end=end,
    )
    positive = sum(1 for row in rows if row["positive"])
    aggregate_base = sum(D(str(row["baseline_equity_delta_usdc"])) for row in rows)
    aggregate_stress = sum(D(str(row["stress_equity_delta_usdc"])) for row in rows)
    max_dd_worsening = max(
        max(
            D(str(row["baseline_drawdown_delta_pp"])),
            D(str(row["stress_drawdown_delta_pp"])),
        )
        for row in rows
    )
    pass_gate = (
        positive >= 2
        and aggregate_base > 0
        and aggregate_stress > 0
        and max_dd_worsening <= D("5")
    )
    return {
        "schema_version": 1,
        "reference": REFERENCE.key,
        "candidate": candidate.key,
        "windows": rows,
        "positive_windows": positive,
        "minimum_positive_windows": 2,
        "aggregate_baseline_equity_delta_usdc": str(aggregate_base),
        "aggregate_stress_equity_delta_usdc": str(aggregate_stress),
        "max_drawdown_worsening_pp": str(max_dd_worsening),
        "max_allowed_drawdown_worsening_pp": "5",
        "cross_window_pass": pass_gate,
        "research_only": True,
        "activation_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout-evidence",
        type=Path,
        default=Path("evidence/capital-budget-optimizer.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/capital-layout-cross-window.json"),
    )
    args = parser.parse_args(argv)
    evidence = json.loads(args.layout_evidence.read_text(encoding="utf-8"))
    result = evaluate(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

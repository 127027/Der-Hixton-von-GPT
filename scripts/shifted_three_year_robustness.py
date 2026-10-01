"""Shifted full-three-year robustness checks for autonomous Hixton candidates.

This catches endpoint sensitivity that ordinary train/validation splits can miss.
It evaluates the same incumbent and candidate on several complete three-year
windows shifted backward from the current closed-bar endpoint.

Research only: no strategy activation, Paper mutation, credentials or orders.
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
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.capital import capital_plan
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map
from scripts.capital_budget_optimizer import Layout
from scripts.coin_optimization_cycle import Candidate, _candidate_from_payload, _rules

OFFSETS_HOURS = (0, -1, -6, -24, -168)
MAX_DRAWDOWN_WORSENING_PP = D("5")
MIN_NON_REGRESSIVE_WINDOWS = 4


def _layout_from_key(value: str) -> Layout:
    policy, geometry = value.split(":", 1)
    slots_text, tranche_text = geometry.split("x", 1)
    return Layout(policy, int(slots_text), D(tranche_text))


def _selected_layout(evidence: dict[str, Any] | None) -> Layout | None:
    if not evidence:
        return None
    comparison = evidence.get("frequency_comparison")
    if not isinstance(comparison, dict):
        return None
    raw = comparison.get("strict_frequency_improvements")
    strict = [str(value) for value in raw] if isinstance(raw, list) else []
    if not strict:
        return None
    best = evidence.get("best_robust")
    best_key = str(best.get("layout")) if isinstance(best, dict) else ""
    return _layout_from_key(best_key if best_key in strict else strict[0])


def _selected_coin_profiles(
    evidence: dict[str, Any] | None,
) -> tuple[dict[str, Candidate], list[str]] | tuple[None, list[str]]:
    if not evidence:
        return None, []
    per_coin = evidence.get("per_coin")
    if not isinstance(per_coin, dict):
        return None, []
    current = _candidate_map(research=False)
    candidate = dict(current)
    accepted: list[str] = []
    for symbol, raw in per_coin.items():
        if not isinstance(raw, dict) or raw.get("accepted") is not True:
            continue
        profile = raw.get("accepted_profile")
        if not isinstance(profile, dict):
            continue
        candidate[str(symbol)] = _candidate_from_payload(
            f"shifted_{symbol}", profile
        )
        accepted.append(str(symbol))
    return (candidate if accepted else None), sorted(accepted)


def _portfolio(
    *,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Candidate],
    start: Any,
    end: Any,
    costs: Any,
    layout: Layout,
) -> dict[str, object]:
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=D("250"),
        target_notional=layout.tranche,
        slot_count=layout.slots,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=V6_COIN_STRATEGY.parameters,
        strategy_parameters_by_symbol={
            symbol: profile.parameters for symbol, profile in profiles.items()
        },
        trade_policies_by_symbol={
            symbol: profile.policy for symbol, profile in profiles.items()
        },
        strategy_semantics=V6_COIN_STRATEGY.semantics,
        strategy_version="HIXTON-V6-SHIFTED-WINDOW-ROBUSTNESS",
        slot_allocation=layout.policy,
        apply_risk_limits=True,
        symbols=V6_COIN_STRATEGY.symbols,
    )
    return {
        "ending_equity": str(result.metrics.ending_equity),
        "position_cycles": result.metrics.completed_trades,
        "slot_trades": result.metrics.completed_slot_trades,
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
    }


def _compare_windows(
    *,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    incumbent_profiles: dict[str, Candidate],
    candidate_profiles: dict[str, Candidate],
    incumbent_layout: Layout,
    candidate_layout: Layout,
    report_start: Any,
    report_end: Any,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for offset in OFFSETS_HOURS:
        delta = timedelta(hours=offset)
        start = report_start + delta
        end = report_end + delta

        incumbent_base = _portfolio(
            candles=candles, rules=rules, profiles=incumbent_profiles,
            start=start, end=end, costs=BASELINE_COSTS, layout=incumbent_layout,
        )
        candidate_base = _portfolio(
            candles=candles, rules=rules, profiles=candidate_profiles,
            start=start, end=end, costs=BASELINE_COSTS, layout=candidate_layout,
        )
        incumbent_stress = _portfolio(
            candles=candles, rules=rules, profiles=incumbent_profiles,
            start=start, end=end, costs=STRESS_COSTS, layout=incumbent_layout,
        )
        candidate_stress = _portfolio(
            candles=candles, rules=rules, profiles=candidate_profiles,
            start=start, end=end, costs=STRESS_COSTS, layout=candidate_layout,
        )

        base_delta = D(str(candidate_base["ending_equity"])) - D(
            str(incumbent_base["ending_equity"])
        )
        stress_delta = D(str(candidate_stress["ending_equity"])) - D(
            str(incumbent_stress["ending_equity"])
        )
        dd_worsening = max(
            D(str(candidate_base["max_drawdown_pct"]))
            - D(str(incumbent_base["max_drawdown_pct"])),
            D(str(candidate_stress["max_drawdown_pct"]))
            - D(str(incumbent_stress["max_drawdown_pct"])),
        )
        rows.append(
            {
                "offset_hours": offset,
                "start_utc": start.isoformat(),
                "end_utc": end.isoformat(),
                "incumbent_baseline_equity": incumbent_base["ending_equity"],
                "candidate_baseline_equity": candidate_base["ending_equity"],
                "baseline_equity_delta_usdc": str(base_delta),
                "incumbent_stress_equity": incumbent_stress["ending_equity"],
                "candidate_stress_equity": candidate_stress["ending_equity"],
                "stress_equity_delta_usdc": str(stress_delta),
                "position_cycle_delta": (
                    int(candidate_base["position_cycles"])
                    - int(incumbent_base["position_cycles"])
                ),
                "max_drawdown_worsening_pp": str(dd_worsening),
                "non_regressive": (
                    base_delta >= 0
                    and stress_delta >= 0
                    and dd_worsening <= MAX_DRAWDOWN_WORSENING_PP
                ),
            }
        )

    good = sum(1 for row in rows if row["non_regressive"])
    base_total = sum(D(str(row["baseline_equity_delta_usdc"])) for row in rows)
    stress_total = sum(D(str(row["stress_equity_delta_usdc"])) for row in rows)
    current = next(row for row in rows if row["offset_hours"] == 0)
    passed = (
        good >= MIN_NON_REGRESSIVE_WINDOWS
        and base_total > 0
        and stress_total > 0
        and D(str(current["baseline_equity_delta_usdc"])) >= 0
        and D(str(current["stress_equity_delta_usdc"])) >= 0
    )
    incumbent_values = [D(str(row["incumbent_baseline_equity"])) for row in rows]
    return {
        "offsets_hours": list(OFFSETS_HOURS),
        "windows": rows,
        "non_regressive_windows": good,
        "minimum_non_regressive_windows": MIN_NON_REGRESSIVE_WINDOWS,
        "aggregate_baseline_delta_usdc": str(base_total),
        "aggregate_stress_delta_usdc": str(stress_total),
        "incumbent_endpoint_sensitivity_usdc": str(
            max(incumbent_values) - min(incumbent_values)
        ),
        "shifted_window_pass": passed,
    }


def evaluate(
    coin_evidence: dict[str, Any] | None,
    layout_evidence: dict[str, Any] | None,
) -> dict[str, object]:
    _, report_start, report_end = safe_closed_window()
    earliest = report_start + timedelta(hours=min(OFFSETS_HOURS))
    rules = _rules()
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=earliest,
        report_end_utc=report_end,
        execution_rules=rules,
    )
    candles = history.candles_by_symbol
    incumbent_profiles = _candidate_map(research=False)
    plan = capital_plan(D("250"))
    incumbent_layout = Layout(
        plan.allocation_policy, plan.slot_count, plan.target_notional_usdc
    )

    layout_candidate = _selected_layout(layout_evidence)
    layout_result: dict[str, object]
    if layout_candidate is None:
        layout_result = {
            "candidate": None,
            "shifted_window_pass": False,
            "reason": "no_strict_layout_candidate",
        }
    else:
        layout_result = {
            "candidate": layout_candidate.key,
            **_compare_windows(
                candles=candles,
                rules=rules,
                incumbent_profiles=incumbent_profiles,
                candidate_profiles=incumbent_profiles,
                incumbent_layout=incumbent_layout,
                candidate_layout=layout_candidate,
                report_start=report_start,
                report_end=report_end,
            ),
        }

    coin_profiles, accepted_symbols = _selected_coin_profiles(coin_evidence)
    coin_result: dict[str, object]
    if coin_profiles is None:
        coin_result = {
            "accepted_symbols": [],
            "shifted_window_pass": False,
            "reason": "no_accepted_coin_candidate",
        }
    else:
        coin_result = {
            "accepted_symbols": accepted_symbols,
            **_compare_windows(
                candles=candles,
                rules=rules,
                incumbent_profiles=incumbent_profiles,
                candidate_profiles=coin_profiles,
                incumbent_layout=incumbent_layout,
                candidate_layout=incumbent_layout,
                report_start=report_start,
                report_end=report_end,
            ),
        }

    return {
        "schema_version": 1,
        "study": "SHIFTED_FULL_THREE_YEAR_ENDPOINT_ROBUSTNESS",
        "research_only": True,
        "activation_performed": False,
        "reference_strategy_version": V6_COIN_STRATEGY.version,
        "layout": layout_result,
        "coin_profile": coin_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coin-evidence",
        type=Path,
        default=Path("evidence/coin-optimization-cycle.json"),
    )
    parser.add_argument(
        "--layout-evidence",
        type=Path,
        default=Path("evidence/capital-budget-optimizer.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/shifted-three-year-robustness.json"),
    )
    args = parser.parse_args(argv)

    coin = json.loads(args.coin_evidence.read_text(encoding="utf-8"))
    layout = json.loads(args.layout_evidence.read_text(encoding="utf-8"))
    result = evaluate(coin, layout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    main()

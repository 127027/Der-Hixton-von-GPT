"""Future-readiness rejection gate for autonomous Hixton candidates.

The purpose is not to predict the future. It asks whether an already-selected
candidate remains useful across recent, differently sized proxy windows and under
more adverse execution costs. These windows are sealed rejection evidence:
their detailed outcomes must not be used to tune the next candidate.
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, CostModel
from hixton.domain.capital import capital_plan
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map
from scripts.capital_budget_optimizer import Layout
from scripts.coin_optimization_cycle import Candidate, _rules
from scripts.shifted_three_year_robustness import (
    _portfolio,
    _selected_coin_profiles,
    _selected_layout,
)

RECENT_WINDOWS_DAYS = (90, 180, 365, 730)
EXTREME_COSTS = CostModel(
    name="future_extreme",
    fee_bps_per_side=D("15"),
    spread_bps_per_side=D("20"),
    slippage_bps_per_side=D("40"),
)
MIN_RECENT_NON_REGRESSIVE = 3
MAX_DRAWDOWN_WORSENING_PP = D("5")


def _window_compare(
    *,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    incumbent_profiles: dict[str, Candidate],
    candidate_profiles: dict[str, Candidate],
    incumbent_layout: Layout,
    candidate_layout: Layout,
    start: Any,
    end: Any,
    costs: Any,
) -> dict[str, object]:
    incumbent = _portfolio(
        candles=candles,
        rules=rules,
        profiles=incumbent_profiles,
        start=start,
        end=end,
        costs=costs,
        layout=incumbent_layout,
    )
    candidate = _portfolio(
        candles=candles,
        rules=rules,
        profiles=candidate_profiles,
        start=start,
        end=end,
        costs=costs,
        layout=candidate_layout,
    )
    equity_delta = D(str(candidate["ending_equity"])) - D(
        str(incumbent["ending_equity"])
    )
    dd_worsening = D(str(candidate["max_drawdown_pct"])) - D(
        str(incumbent["max_drawdown_pct"])
    )
    return {
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "cost_model": getattr(costs, "name", "unknown"),
        "incumbent_ending_equity": incumbent["ending_equity"],
        "candidate_ending_equity": candidate["ending_equity"],
        "equity_delta_usdc": str(equity_delta),
        "incumbent_max_drawdown_pct": incumbent["max_drawdown_pct"],
        "candidate_max_drawdown_pct": candidate["max_drawdown_pct"],
        "drawdown_worsening_pp": str(dd_worsening),
        "position_cycle_delta": (
            int(candidate["position_cycles"]) - int(incumbent["position_cycles"])
        ),
        "non_regressive": (
            equity_delta >= 0 and dd_worsening <= MAX_DRAWDOWN_WORSENING_PP
        ),
    }


def _evaluate_candidate(
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
    recent_rows: list[dict[str, object]] = []
    for days in RECENT_WINDOWS_DAYS:
        start = max(report_start, report_end - timedelta(days=days))
        recent_rows.append(
            {
                "window_days": days,
                **_window_compare(
                    candles=candles,
                    rules=rules,
                    incumbent_profiles=incumbent_profiles,
                    candidate_profiles=candidate_profiles,
                    incumbent_layout=incumbent_layout,
                    candidate_layout=candidate_layout,
                    start=start,
                    end=report_end,
                    costs=STRESS_COSTS,
                ),
            }
        )

    extreme = _window_compare(
        candles=candles,
        rules=rules,
        incumbent_profiles=incumbent_profiles,
        candidate_profiles=candidate_profiles,
        incumbent_layout=incumbent_layout,
        candidate_layout=candidate_layout,
        start=report_start,
        end=report_end,
        costs=EXTREME_COSTS,
    )
    baseline = _window_compare(
        candles=candles,
        rules=rules,
        incumbent_profiles=incumbent_profiles,
        candidate_profiles=candidate_profiles,
        incumbent_layout=incumbent_layout,
        candidate_layout=candidate_layout,
        start=report_start,
        end=report_end,
        costs=BASELINE_COSTS,
    )

    good = sum(1 for row in recent_rows if row["non_regressive"])
    recent_aggregate = sum(D(str(row["equity_delta_usdc"])) for row in recent_rows)
    passed = (
        good >= MIN_RECENT_NON_REGRESSIVE
        and recent_aggregate > 0
        and bool(extreme["non_regressive"])
        and D(str(extreme["equity_delta_usdc"])) >= 0
        and bool(baseline["non_regressive"])
    )
    return {
        "sealed_rejection_only": True,
        "detailed_results_must_not_select_or_tune_next_candidate": True,
        "recent_proxy_windows": recent_rows,
        "recent_non_regressive_windows": good,
        "minimum_recent_non_regressive_windows": MIN_RECENT_NON_REGRESSIVE,
        "aggregate_recent_equity_delta_usdc": str(recent_aggregate),
        "full_window_baseline": baseline,
        "full_window_extreme_cost": extreme,
        "future_readiness_pass": passed,
    }


def evaluate(
    coin_evidence: dict[str, Any] | None,
    layout_evidence: dict[str, Any] | None,
) -> dict[str, object]:
    _, report_start, report_end = safe_closed_window()
    rules = _rules()
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=report_start,
        report_end_utc=report_end,
        execution_rules=rules,
    )
    candles = history.candles_by_symbol
    incumbent_profiles = _candidate_map(research=False)
    plan = capital_plan(D("250"))
    incumbent_layout = Layout(
        plan.allocation_policy, plan.slot_count, plan.target_notional_usdc
    )

    coin_profiles, accepted_symbols = _selected_coin_profiles(coin_evidence)
    if coin_profiles is None:
        coin_result: dict[str, object] = {
            "accepted_symbols": [],
            "future_readiness_pass": False,
            "reason": "no_accepted_coin_candidate",
        }
    else:
        coin_result = {
            "accepted_symbols": accepted_symbols,
            **_evaluate_candidate(
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

    layout_candidate = _selected_layout(layout_evidence)
    if layout_candidate is None:
        layout_result: dict[str, object] = {
            "candidate": None,
            "future_readiness_pass": False,
            "reason": "no_strict_layout_candidate",
        }
    else:
        layout_result = {
            "candidate": layout_candidate.key,
            **_evaluate_candidate(
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

    return {
        "schema_version": 1,
        "study": "SEALED_FUTURE_READINESS_REJECTION_GATE",
        "research_only": True,
        "activation_performed": False,
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "recent_windows_days": list(RECENT_WINDOWS_DAYS),
        "extreme_cost_model": {
            "fee_bps_per_side": str(EXTREME_COSTS.fee_bps_per_side),
            "spread_bps_per_side": str(EXTREME_COSTS.spread_bps_per_side),
            "slippage_bps_per_side": str(EXTREME_COSTS.slippage_bps_per_side),
        },
        "coin_profile": coin_result,
        "capital_layout": layout_result,
    }


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


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
        default=Path("evidence/future-readiness-gate.json"),
    )
    args = parser.parse_args(argv)
    result = evaluate(_load(args.coin_evidence), _load(args.layout_evidence))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

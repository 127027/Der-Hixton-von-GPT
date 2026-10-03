"""Bounded holding-duration research for MISSION-CAPITAL-ACTIVITY-250.

This experiment keeps entries, coin profiles, 250-USDC capital, allocator and execution
rules fixed. It changes only the maximum holding duration. Candidate selection is based
on the training segment; holdout and full-window evidence may reject but never choose a
different parameter. Product behavior is untouched because the backtest holding cap is
research-only and defaults to None.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.domain.capital import capital_plan
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map
from scripts.capital_budget_optimizer import Layout, _run
from scripts.coin_optimization_cycle import _rules

CAPITAL = D("250")
HOLDING_CAPS_HOURS = (72, 120, 168)
EQUITY_FLOOR_RATIO = D("0.85")
MAX_DRAWDOWN_WORSENING_PP = D("5")
MINIMUM_CYCLES_3Y = 157
GOOD_CYCLES_3Y = 365
STRETCH_CYCLES_3Y = 1095


def _tier(cycles: int) -> str:
    if cycles >= STRETCH_CYCLES_3Y:
        return "STRETCH_1_PER_DAY"
    if cycles >= GOOD_CYCLES_3Y:
        return "GOOD_1_PER_3_DAYS"
    if cycles >= MINIMUM_CYCLES_3Y:
        return "MINIMUM_1_PER_7_DAYS"
    return "BELOW_MINIMUM"


def _pair(
    *,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Any],
    layout: Layout,
    start: Any,
    end: Any,
    cap: int | None,
) -> dict[str, Any]:
    base = _run(
        candles=candles,
        rules=rules,
        profiles=profiles,
        start=start,
        end=end,
        layout=layout,
        costs=BASELINE_COSTS,
        research_max_holding_hours=cap,
    )
    stress = _run(
        candles=candles,
        rules=rules,
        profiles=profiles,
        start=start,
        end=end,
        layout=layout,
        costs=STRESS_COSTS,
        research_max_holding_hours=cap,
    )
    return {"baseline": base, "stress": stress}


def _comparison(candidate: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    cb = candidate["baseline"]
    cs = candidate["stress"]
    rb = reference["baseline"]
    rs = reference["stress"]
    base_ratio = D(str(cb["ending_equity"])) / D(str(rb["ending_equity"]))
    stress_ratio = D(str(cs["ending_equity"])) / D(str(rs["ending_equity"]))
    base_dd = D(str(cb["max_drawdown_pct"])) - D(str(rb["max_drawdown_pct"]))
    stress_dd = D(str(cs["max_drawdown_pct"])) - D(str(rs["max_drawdown_pct"]))
    cycle_delta = int(cb["position_cycles"]) - int(rb["position_cycles"])
    return {
        "baseline_equity_ratio": str(base_ratio),
        "stress_equity_ratio": str(stress_ratio),
        "baseline_equity_delta_usdc": str(
            D(str(cb["ending_equity"])) - D(str(rb["ending_equity"]))
        ),
        "stress_equity_delta_usdc": str(
            D(str(cs["ending_equity"])) - D(str(rs["ending_equity"]))
        ),
        "position_cycle_delta": cycle_delta,
        "position_cycles": int(cb["position_cycles"]),
        "position_cycles_per_day": cb["position_cycles_per_day"],
        "slot_utilization_pct": cb["trade_timing"]["slot_utilization_pct"],
        "average_deployed_notional_usdc": cb["trade_timing"][
            "average_deployed_notional_usdc"
        ],
        "zero_position_pct": cb["trade_timing"]["zero_position_pct"],
        "longest_idle_hours": cb["trade_timing"]["longest_idle_hours"],
        "baseline_drawdown_worsening_pp": str(base_dd),
        "stress_drawdown_worsening_pp": str(stress_dd),
        "equity_floor_pass": (
            base_ratio >= EQUITY_FLOOR_RATIO and stress_ratio >= EQUITY_FLOOR_RATIO
        ),
        "drawdown_pass": (
            base_dd <= MAX_DRAWDOWN_WORSENING_PP
            and stress_dd <= MAX_DRAWDOWN_WORSENING_PP
        ),
        "activity_gain": cycle_delta > 0,
    }


def _reject_gate(comp: dict[str, Any]) -> bool:
    return (
        bool(comp["equity_floor_pass"])
        and bool(comp["drawdown_pass"])
        and bool(comp["activity_gain"])
    )


def main() -> None:
    _, report_start, report_end = safe_closed_window()
    holdout_start = report_end - timedelta(days=365)
    if holdout_start <= report_start:
        raise RuntimeError("three-year window is too short for sealed one-year holdout")

    rules = _rules()
    profiles = _candidate_map(research=False)
    plan = capital_plan(CAPITAL)
    layout = Layout(plan.allocation_policy, plan.slot_count, plan.target_notional_usdc)
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=report_start,
        report_end_utc=report_end,
        execution_rules=rules,
    )
    candles = history.candles_by_symbol

    windows = {
        "training": (report_start, holdout_start),
        "holdout": (holdout_start, report_end),
        "full_three_year": (report_start, report_end),
    }
    reference = {
        name: _pair(
            candles=candles,
            rules=rules,
            profiles=profiles,
            layout=layout,
            start=start,
            end=end,
            cap=None,
        )
        for name, (start, end) in windows.items()
    }

    candidates: list[dict[str, Any]] = []
    for cap in HOLDING_CAPS_HOURS:
        evidence: dict[str, Any] = {
            "max_holding_hours": cap,
            "training_only_selection": True,
            "windows": {},
        }
        for name, (start, end) in windows.items():
            pair = _pair(
                candles=candles,
                rules=rules,
                profiles=profiles,
                layout=layout,
                start=start,
                end=end,
                cap=cap,
            )
            comp = _comparison(pair, reference[name])
            evidence["windows"][name] = {
                "baseline": pair["baseline"],
                "stress": pair["stress"],
                "comparison": comp,
            }
        train = evidence["windows"]["training"]["comparison"]
        evidence["training_gate_pass"] = _reject_gate(train)
        candidates.append(evidence)

    # Freeze ranking from training only. Holdout/full data may only reject.
    training_ranked = sorted(
        candidates,
        key=lambda item: (
            bool(item["training_gate_pass"]),
            int(item["windows"]["training"]["comparison"]["position_cycle_delta"]),
            min(
                D(item["windows"]["training"]["comparison"]["baseline_equity_ratio"]),
                D(item["windows"]["training"]["comparison"]["stress_equity_ratio"]),
            ),
        ),
        reverse=True,
    )
    frozen_order = [int(item["max_holding_hours"]) for item in training_ranked]

    for item in candidates:
        holdout = item["windows"]["holdout"]["comparison"]
        full = item["windows"]["full_three_year"]["comparison"]
        cycles = int(full["position_cycles"])
        item["holdout_rejection_pass"] = _reject_gate(holdout)
        item["full_rejection_pass"] = _reject_gate(full)
        item["frequency_tier"] = _tier(cycles)
        item["mission_minimum_frequency_met"] = cycles >= MINIMUM_CYCLES_3Y
        item["validated_activity_candidate"] = (
            bool(item["training_gate_pass"])
            and bool(item["holdout_rejection_pass"])
            and bool(item["full_rejection_pass"])
            and bool(item["mission_minimum_frequency_met"])
        )

    validated_by_cap = {
        int(item["max_holding_hours"]): item
        for item in candidates
        if item["validated_activity_candidate"]
    }
    selected = next(
        (validated_by_cap[cap] for cap in frozen_order if cap in validated_by_cap),
        None,
    )

    output = {
        "schema_version": 1,
        "study": "BOUNDED_HOLDING_DURATION_ACTIVITY_RESEARCH",
        "mission": "MISSION-CAPITAL-ACTIVITY-250",
        "research_only": True,
        "activation_performed": False,
        "causal_family": "holding_duration",
        "fixed": {
            "capital_usdc": str(CAPITAL),
            "layout": layout.key,
            "coin_profiles": V6_COIN_STRATEGY.version,
            "entry_logic_unchanged": True,
            "cost_models": [BASELINE_COSTS.name, STRESS_COSTS.name],
        },
        "selection_protocol": {
            "training_window_selects": True,
            "holdout_may_reject_not_select": True,
            "full_window_may_reject_not_select": True,
            "equity_floor_ratio": str(EQUITY_FLOOR_RATIO),
            "max_drawdown_worsening_pp": str(MAX_DRAWDOWN_WORSENING_PP),
            "minimum_cycles_3y": MINIMUM_CYCLES_3Y,
            "good_cycles_3y": GOOD_CYCLES_3Y,
            "stretch_cycles_3y": STRETCH_CYCLES_3Y,
        },
        "windows": {
            name: {"start_utc": start.isoformat(), "end_utc": end.isoformat()}
            for name, (start, end) in windows.items()
        },
        "reference": reference,
        "training_ranked_caps_hours": frozen_order,
        "candidates": candidates,
        "selected_validated_cap_hours": (
            None if selected is None else int(selected["max_holding_hours"])
        ),
        "selected_frequency_tier": (
            None if selected is None else selected["frequency_tier"]
        ),
        "limitations": [
            "Historical simulation is not a forecast.",
            "A time exit can free capital but can also truncate large trend winners.",
            "The research-only time cap is not implemented in Paper or Live.",
            "Any engineering candidate still requires shifted windows, future-readiness, red-team, A09 and A11.",
        ],
    }
    path = Path("evidence") / "holding-duration-research.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

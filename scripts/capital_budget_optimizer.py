"""Research-only capital budget optimizer for a fixed maximum account balance.

Searches how a 1,000-USDC account would have been allocated most effectively
across slot count, tranche size and allocation policy while keeping the same
coin profiles, strategy semantics, market history, Binance execution rules and
risk limits. It never mutates canonical V6, Paper state or Live state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_DOWN
from decimal import Decimal as D
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map, _profile_hashes
from scripts.coin_optimization_cycle import _rules

CAPITAL = D("1000")
MIN_TRANCHE = D("50")
STEP = D("5")
FULL_UTILIZATION_SLOT_RANGE = range(1, 21)


@dataclass(frozen=True, slots=True)
class Layout:
    policy: str
    slots: int
    tranche: D

    @property
    def commitment(self) -> D:
        return self.tranche * self.slots

    @property
    def key(self) -> str:
        return f"{self.policy}:{self.slots}x{self.tranche}"


def _floor_step(value: D) -> D:
    return (value / STEP).to_integral_value(rounding=ROUND_DOWN) * STEP


def _layouts() -> tuple[Layout, ...]:
    found: dict[str, Layout] = {}

    # Primary search axis: every practical ranked-repeat slot count using as much
    # of the 1,000-USDC account as possible, rounded down to a 5-USDC tranche.
    for slots in FULL_UTILIZATION_SLOT_RANGE:
        tranche = _floor_step(CAPITAL / D(slots))
        if tranche < MIN_TRANCHE:
            continue
        layout = Layout(RANKED_REPEAT, slots, tranche)
        found[layout.key] = layout

    # Explicit lower-utilization probes answer the owner's requirement that
    # leaving capital idle may win if it materially improves opportunity quality.
    explicit = (
        Layout(RANKED_REPEAT, 3, D("80")),
        Layout(RANKED_REPEAT, 5, D("50")),
        Layout(RANKED_REPEAT, 2, D("250")),
        Layout(RANKED_REPEAT, 3, D("250")),
        Layout(RANKED_REPEAT, 4, D("125")),
        Layout(RANKED_REPEAT, 4, D("200")),
        Layout(RANKED_REPEAT, 5, D("100")),
        Layout(RANKED_REPEAT, 5, D("150")),
        Layout(RANKED_REPEAT, 10, D("50")),
        Layout(RANKED_REPEAT, 12, D("80")),
        Layout(RANKED_REPEAT, 20, D("50")),
        Layout(ONE_PER_SYMBOL, 3, D("80")),
        Layout(ONE_PER_SYMBOL, 5, D("100")),
        Layout(ONE_PER_SYMBOL, 10, D("50")),
        Layout(ONE_PER_SYMBOL, 10, D("100")),
    )
    for layout in explicit:
        if layout.commitment <= CAPITAL:
            found[layout.key] = layout
    return tuple(sorted(found.values(), key=lambda x: (x.policy, x.slots, x.tranche)))


def _run(
    *,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Any],
    start: Any,
    end: Any,
    layout: Layout,
    costs: Any,
) -> dict[str, object]:
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=CAPITAL,
        target_notional=layout.tranche,
        slot_count=layout.slots,
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
        strategy_version="HIXTON-V6-CAPITAL-BUDGET-RESEARCH",
        slot_allocation=layout.policy,
        apply_risk_limits=True,
        symbols=V6_COIN_STRATEGY.symbols,
    )
    no_free = sum(1 for item in result.blocked_signals if item.endswith(":NO_FREE_SLOT"))
    return {
        "layout": layout.key,
        "policy": layout.policy,
        "slot_count": layout.slots,
        "tranche_usdc": str(layout.tranche),
        "max_commitment_usdc": str(layout.commitment),
        "reserve_at_max_commitment_usdc": str(CAPITAL - layout.commitment),
        "capital_utilization_pct": str(layout.commitment / CAPITAL * D("100")),
        "ending_equity": str(result.metrics.ending_equity),
        "net_pnl": str(result.metrics.net_pnl),
        "return_pct": str(result.metrics.return_pct),
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "position_cycles": result.metrics.completed_trades,
        "slot_trades": result.metrics.completed_slot_trades,
        "max_concurrent_slots": result.max_concurrent_positions,
        "blocked_no_free_slot": no_free,
        "risk_halted_at_utc": (
            None if result.risk_halted_at_utc is None else result.risk_halted_at_utc.isoformat()
        ),
    }


def _rank(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: D(str(row["ending_equity"])), reverse=True)


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

    layouts = _layouts()
    baseline_rows: list[dict[str, object]] = []
    for index, layout in enumerate(layouts, start=1):
        row = _run(
            candles=history.candles_by_symbol,
            rules=rules,
            profiles=profiles,
            start=start,
            end=end,
            layout=layout,
            costs=BASELINE_COSTS,
        )
        baseline_rows.append(row)
        print(
            f"baseline {index}/{len(layouts)} {layout.key}: "
            f"{row['ending_equity']} USDC"
        )
    baseline_ranked = _rank(baseline_rows)

    # Stress every serious baseline contender plus reference layouts. This keeps
    # the search broad while avoiding hundreds of redundant full stress replays.
    top_keys = {str(row["layout"]) for row in baseline_ranked[:10]}
    reference_keys = {
        f"{RANKED_REPEAT}:3x80",
        f"{RANKED_REPEAT}:5x50",
        f"{RANKED_REPEAT}:4x250",
        f"{RANKED_REPEAT}:10x100",
        f"{RANKED_REPEAT}:12x80",
        f"{RANKED_REPEAT}:20x50",
        f"{ONE_PER_SYMBOL}:10x100",
    }
    stress_layouts = [
        layout for layout in layouts if layout.key in top_keys | reference_keys
    ]
    stress_rows: list[dict[str, object]] = []
    for index, layout in enumerate(stress_layouts, start=1):
        row = _run(
            candles=history.candles_by_symbol,
            rules=rules,
            profiles=profiles,
            start=start,
            end=end,
            layout=layout,
            costs=STRESS_COSTS,
        )
        stress_rows.append(row)
        print(
            f"stress {index}/{len(stress_layouts)} {layout.key}: "
            f"{row['ending_equity']} USDC"
        )
    stress_by_key = {str(row["layout"]): row for row in stress_rows}

    robust_rows: list[dict[str, object]] = []
    for row in baseline_ranked:
        key = str(row["layout"])
        stress = stress_by_key.get(key)
        if stress is None:
            continue
        merged = dict(row)
        merged["stress_ending_equity"] = stress["ending_equity"]
        merged["stress_return_pct"] = stress["return_pct"]
        merged["stress_max_drawdown_pct"] = stress["max_drawdown_pct"]
        merged["stress_risk_halted_at_utc"] = stress["risk_halted_at_utc"]
        robust_rows.append(merged)

    robust_ranked = sorted(
        robust_rows,
        key=lambda row: (
            D(str(row["stress_ending_equity"])),
            D(str(row["ending_equity"])),
        ),
        reverse=True,
    )

    output = {
        "schema_version": 1,
        "study": "MAX_1000_USDC_CAPITAL_BUDGET_OPTIMIZATION",
        "research_only": True,
        "activation_performed": False,
        "report_start_utc": start.isoformat(),
        "report_end_utc": end.isoformat(),
        "maximum_account_capital_usdc": str(CAPITAL),
        "minimum_tested_tranche_usdc": str(MIN_TRANCHE),
        "profile_hash_by_symbol": _profile_hashes(profiles),
        "candidate_layout_count": len(layouts),
        "baseline_results": baseline_ranked,
        "stress_results": _rank(stress_rows),
        "robust_results": robust_ranked,
        "best_baseline": baseline_ranked[0],
        "best_stress": _rank(stress_rows)[0],
        "best_robust": robust_ranked[0],
        "references": {
            key: next((row for row in baseline_ranked if row["layout"] == key), None)
            for key in sorted(reference_keys)
        },
        "selection_rule": (
            "Full-utilization ranked-repeat slots 1..20 plus targeted lower-utilization "
            "and one-per-symbol probes; stress Top-10 baseline contenders plus fixed "
            "reference layouts; robust leader ranks by stress ending equity then baseline."
        ),
        "limitations": [
            "Historical simulation is not a forecast or guaranteed live result.",
            "Capital layout is optimized on this historical window and can itself overfit.",
            "Unused capital remains cash inside the same 1,000-USDC ledger.",
            "No canonical V6, Paper or Live setting is changed automatically.",
        ],
    }
    path = Path("evidence") / "capital-budget-optimizer.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

"""Research-only 250-USDC capital-layout comparison.

Challenges the current production baseline (2x125 ranked_repeat) against higher-slot
layouts using the exact same canonical V6 coin profiles, three-year history, costs,
Binance execution rules and portfolio risk model. It never mutates canonical V6,
Paper state or Live state and never places an order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path
from statistics import median
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.allocation import RANKED_REPEAT
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map, _profile_hashes
from scripts.coin_optimization_cycle import _rules

STUDY_ID = "FIXED_250_USDC_SLOT_LAYOUT_CHALLENGE"  # Exact-head research trigger.
CAPITAL = D("250")
MIN_TRANCHE = D("50")


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


def _layouts() -> tuple[Layout, ...]:
    # Keep policy/profile/history fixed so the comparison isolates slot geometry.
    # 3x83.33 intentionally leaves one cent cash rather than exceeding 250 USDC.
    return (
        Layout(RANKED_REPEAT, 2, D("125")),
        Layout(RANKED_REPEAT, 3, D("83.33")),
        Layout(RANKED_REPEAT, 4, D("62.50")),
        Layout(RANKED_REPEAT, 5, D("50")),
    )


def _timing(result: Any, layout: Layout, start: datetime, end: datetime) -> dict[str, object]:
    entries = sorted(trade.entry_time_utc.astimezone(UTC) for trade in result.trades)
    gaps = [
        (right - left).total_seconds() / 3600
        for left, right in zip([start, *entries], [*entries, end], strict=True)
    ]
    events: dict[datetime, int] = {}
    for trade in result.trades:
        entry = trade.entry_time_utc.astimezone(UTC)
        exit_at = trade.exit_time_utc.astimezone(UTC)
        slots = int(trade.slot_count)
        events[entry] = events.get(entry, 0) + slots
        events[exit_at] = events.get(exit_at, 0) - slots

    occupancy_hours = {str(value): 0.0 for value in range(layout.slots + 1)}
    occupancy = 0
    previous = start
    max_occupancy = 0
    for at in sorted(events):
        clipped = min(max(at, start), end)
        if clipped > previous:
            if occupancy < 0 or occupancy > layout.slots:
                raise RuntimeError(
                    f"{layout.key}: slot occupancy escaped 0..{layout.slots}: {occupancy}"
                )
            occupancy_hours[str(occupancy)] += (clipped - previous).total_seconds() / 3600
            previous = clipped
        occupancy += events[at]
        max_occupancy = max(max_occupancy, occupancy)
    if previous < end:
        if occupancy < 0 or occupancy > layout.slots:
            raise RuntimeError(
                f"{layout.key}: slot occupancy escaped 0..{layout.slots}: {occupancy}"
            )
        occupancy_hours[str(occupancy)] += (end - previous).total_seconds() / 3600

    entries_by_year: dict[str, int] = {}
    for value in entries:
        key = str(value.year)
        entries_by_year[key] = entries_by_year.get(key, 0) + 1

    return {
        "average_gap_hours_including_window_edges": (sum(gaps) / len(gaps)) if gaps else None,
        "median_gap_hours_including_window_edges": median(gaps) if gaps else None,
        "longest_gap_hours_including_window_edges": max(gaps) if gaps else None,
        "entries_by_year": entries_by_year,
        "max_slot_occupancy": max_occupancy,
        "occupancy_hours_by_slots": occupancy_hours,
        "zero_position_hours": occupancy_hours["0"],
        "full_slot_hours": occupancy_hours[str(layout.slots)],
    }


def _per_symbol(result: Any) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for trade in result.trades:
        item = rows.setdefault(
            trade.symbol,
            {
                "position_cycles": 0,
                "slot_trades": 0,
                "wins": 0,
                "losses": 0,
                "realized_pnl": D("0"),
            },
        )
        item["position_cycles"] = int(item["position_cycles"]) + 1
        item["slot_trades"] = int(item["slot_trades"]) + int(trade.slot_count)
        item["wins"] = int(item["wins"]) + int(trade.realized_pnl > 0)
        item["losses"] = int(item["losses"]) + int(trade.realized_pnl <= 0)
        item["realized_pnl"] = D(str(item["realized_pnl"])) + trade.realized_pnl
    return {
        symbol: {**item, "realized_pnl": str(item["realized_pnl"])}
        for symbol, item in sorted(rows.items())
    }


def _run(
    *,
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Any],
    start: datetime,
    end: datetime,
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
        strategy_version="HIXTON-V6-CAPITAL-250-LAYOUT-RESEARCH",
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
        "wins": result.metrics.winning_trades,
        "losses": result.metrics.losing_trades,
        "win_rate_pct": (
            None if result.metrics.win_rate_pct is None else str(result.metrics.win_rate_pct)
        ),
        "average_holding_hours": (
            None
            if result.metrics.average_holding_hours is None
            else str(result.metrics.average_holding_hours)
        ),
        "max_holding_hours": (
            None
            if result.metrics.max_holding_hours is None
            else str(result.metrics.max_holding_hours)
        ),
        "max_concurrent_slots": result.max_concurrent_positions,
        "blocked_no_free_slot": no_free,
        "risk_halted_at_utc": (
            None if result.risk_halted_at_utc is None else result.risk_halted_at_utc.isoformat()
        ),
        "trade_timing": _timing(result, layout, start, end),
        "per_symbol": _per_symbol(result),
    }


def _rank(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: D(str(row["ending_equity"])), reverse=True)


def main() -> None:
    _, start, end = safe_closed_window()
    rules = _rules()
    # This is a capital-layout experiment, not another coin-profile optimization.
    # Every layout uses the exact active canonical V6 profile map.
    profiles = _candidate_map(research=False)
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
    )

    layouts = _layouts()
    baseline_rows: list[dict[str, object]] = []
    stress_rows: list[dict[str, object]] = []
    for index, layout in enumerate(layouts, start=1):
        baseline = _run(
            candles=history.candles_by_symbol,
            rules=rules,
            profiles=profiles,
            start=start,
            end=end,
            layout=layout,
            costs=BASELINE_COSTS,
        )
        baseline_rows.append(baseline)
        print(f"baseline {index}/{len(layouts)} {layout.key}: {baseline['ending_equity']} USDC")

        stress = _run(
            candles=history.candles_by_symbol,
            rules=rules,
            profiles=profiles,
            start=start,
            end=end,
            layout=layout,
            costs=STRESS_COSTS,
        )
        stress_rows.append(stress)
        print(f"stress {index}/{len(layouts)} {layout.key}: {stress['ending_equity']} USDC")

    baseline_ranked = _rank(baseline_rows)
    stress_ranked = _rank(stress_rows)
    stress_by_key = {str(row["layout"]): row for row in stress_rows}
    robust_rows: list[dict[str, object]] = []
    for row in baseline_ranked:
        stress = stress_by_key[str(row["layout"])]
        merged = dict(row)
        merged["stress_ending_equity"] = stress["ending_equity"]
        merged["stress_return_pct"] = stress["return_pct"]
        merged["stress_max_drawdown_pct"] = stress["max_drawdown_pct"]
        merged["stress_position_cycles"] = stress["position_cycles"]
        merged["stress_blocked_no_free_slot"] = stress["blocked_no_free_slot"]
        robust_rows.append(merged)
    robust_ranked = sorted(
        robust_rows,
        key=lambda row: (
            D(str(row["stress_ending_equity"])),
            D(str(row["ending_equity"])),
        ),
        reverse=True,
    )

    references = {
        row["layout"]: row
        for row in baseline_rows
    }
    output = {
        "schema_version": 2,
        "study": STUDY_ID,
        "research_only": True,
        "activation_performed": False,
        "report_start_utc": start.isoformat(),
        "report_end_utc": end.isoformat(),
        "maximum_account_capital_usdc": str(CAPITAL),
        "minimum_tested_tranche_usdc": str(MIN_TRANCHE),
        "profile_source": "CURRENT_CANONICAL_V6",
        "profile_hash_by_symbol": _profile_hashes(profiles),
        "candidate_layout_count": len(layouts),
        "baseline_results": baseline_ranked,
        "stress_results": stress_ranked,
        "robust_results": robust_ranked,
        "best_baseline": baseline_ranked[0],
        "best_stress": stress_ranked[0],
        "best_robust": robust_ranked[0],
        "references": references,
        "selection_rule": (
            "Compare 2x125, 3x83.33, 4x62.50 and 5x50 ranked_repeat under identical "
            "canonical V6 profiles/history/risk/cost assumptions. No automatic promotion."
        ),
        "limitations": [
            "Historical simulation is not a forecast or guaranteed live result.",
            "Slot geometry can overfit a historical window.",
            "Unused capital remains cash inside the same 250-USDC ledger.",
            "No canonical V6, Paper or Live setting is changed automatically.",
        ],
    }
    path = Path("evidence") / "capital-budget-optimizer.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

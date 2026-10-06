"""Controlled shared-capital slot-layout research for the 15-market candidate.

Controlled variable: slot count / allocation policy only.
Coin profiles, history, costs, Core priority and Satellite rules stay frozen.
No Paper/Live state is touched and no orders are sent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.satellite_portfolio import RouterConfig, run_filler_router_portfolio
from hixton.data.binance import BinancePublicClient
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.satellite_layer import (
    ACTIVE_SHARED_SATELLITES,
    CORE_SYMBOLS,
    SATELLITE_SYMBOLS,
)

from validate_15coin_satellite_integration import _histories, _maps, _rules

D = Decimal
CENT = D("0.01")
OUTPUT = Path("evidence/slot-layout-matrix.json")


@dataclass(frozen=True, slots=True)
class Layout:
    slots: int
    policy: str

    @property
    def name(self) -> str:
        suffix = "RR" if self.policy == RANKED_REPEAT else "OPS"
        return f"{self.slots}S_{suffix}"


LAYOUTS = (
    Layout(2, RANKED_REPEAT),
    Layout(3, RANKED_REPEAT),
    Layout(4, RANKED_REPEAT),
    Layout(5, RANKED_REPEAT),
    Layout(5, ONE_PER_SYMBOL),
)

UNIVERSES = {
    "CORE10": (),
    "VALIDATED12": ACTIVE_SHARED_SATELLITES,
    "ALL15": SATELLITE_SYMBOLS,
}


def _tranche(max_capital: D, slots: int) -> tuple[D, D]:
    value = (max_capital / D(slots)).quantize(CENT, rounding=ROUND_DOWN)
    reserve = max_capital - value * slots
    if value < D("50"):
        raise ValueError(
            f"{max_capital} with {slots} slots produces tranche {value} below 50 USDC"
        )
    return value, reserve


def _occupancy(result) -> dict[str, object]:
    deltas: dict[object, int] = {}
    for trade in result.trades:
        deltas[trade.entry_time_utc] = deltas.get(trade.entry_time_utc, 0) + trade.slot_count
        deltas[trade.exit_time_utc] = deltas.get(trade.exit_time_utc, 0) - trade.slot_count

    hours = {slot: D("0") for slot in range(result.slot_count + 1)}
    occupied = 0
    previous = result.report_start_utc
    max_slots = 0
    for at in sorted(deltas):
        clipped = min(max(at, result.report_start_utc), result.report_end_utc)
        if clipped > previous:
            if occupied not in hours:
                raise RuntimeError(f"slot occupancy escaped range: {occupied}")
            hours[occupied] += D(str((clipped - previous).total_seconds() / 3600))
            previous = clipped
        occupied += deltas[at]
        if occupied < 0 or occupied > result.slot_count:
            raise RuntimeError(f"slot occupancy escaped range: {occupied}")
        max_slots = max(max_slots, occupied)
    if previous < result.report_end_utc:
        hours[occupied] += D(
            str((result.report_end_utc - previous).total_seconds() / 3600)
        )

    total_hours = sum(hours.values(), D("0"))
    slot_hours = sum(D(slot) * value for slot, value in hours.items())
    utilization = (
        slot_hours / (D(result.slot_count) * total_hours) * D("100")
        if total_hours
        else D("0")
    )
    zero = hours[0]
    full = hours[result.slot_count]
    partial = total_hours - zero - full
    return {
        "hours_by_slots": {str(k): str(v) for k, v in hours.items()},
        "zero_slot_hours": str(zero),
        "partial_slot_hours": str(partial),
        "full_slot_hours": str(full),
        "slot_utilization_pct": str(utilization),
        "max_slots_observed": max_slots,
    }


def _metrics(result, events) -> dict[str, object]:
    m = result.metrics
    sat_trades = [t for t in result.trades if t.symbol in SATELLITE_SYMBOLS]
    core_trades = [t for t in result.trades if t.symbol in CORE_SYMBOLS]
    return {
        "ending_equity": str(m.ending_equity),
        "net_pnl": str(m.net_pnl),
        "return_pct": str(m.return_pct),
        "max_drawdown_pct": str(m.max_drawdown_pct),
        "completed_trades": m.completed_trades,
        "completed_slot_trades": m.completed_slot_trades,
        "winning_trades": m.winning_trades,
        "losing_trades": m.losing_trades,
        "win_rate_pct": None if m.win_rate_pct is None else str(m.win_rate_pct),
        "profit_factor": None if m.profit_factor is None else str(m.profit_factor),
        "average_holding_hours": (
            None if m.average_holding_hours is None else str(m.average_holding_hours)
        ),
        "max_holding_hours": (
            None if m.max_holding_hours is None else str(m.max_holding_hours)
        ),
        "total_fees": str(m.total_fees),
        "exposure_pct": str(m.exposure_pct),
        "no_free_slot_blocks": sum(
            ":NO_FREE_SLOT" in blocked for blocked in result.blocked_signals
        ),
        "strict_idle_handoffs": sum(
            event.get("decision") == "STRICT_IDLE_HANDOFF" for event in events
        ),
        "satellite_trades": len(sat_trades),
        "satellite_pnl": str(sum((t.realized_pnl for t in sat_trades), D("0"))),
        "core_trades": len(core_trades),
        "core_pnl": str(sum((t.realized_pnl for t in core_trades), D("0"))),
        "per_symbol": {
            symbol: {
                "trades": sum(t.symbol == symbol for t in result.trades),
                "slot_trades": sum(
                    t.slot_count for t in result.trades if t.symbol == symbol
                ),
                "net_pnl": str(
                    sum(
                        (t.realized_pnl for t in result.trades if t.symbol == symbol),
                        D("0"),
                    )
                ),
            }
            for symbol in result.symbols
        },
        **_occupancy(result),
    }


def _run(
    *,
    max_capital: D,
    layout: Layout,
    satellites: tuple[str, ...],
    costs,
    candles,
    rules,
    report_start,
    report_end,
):
    parameters, policies, semantics, filters, horizons, reentry = _maps()
    tranche, reserve = _tranche(max_capital, layout.slots)
    symbols = CORE_SYMBOLS + satellites
    result, events = run_filler_router_portfolio(
        candles_by_symbol={s: candles[s] for s in symbols},
        report_start_utc=report_start,
        report_end_utc=report_end,
        starting_cash=max_capital,
        target_notional=tranche,
        slot_count=layout.slots,
        costs=costs,
        execution_rules={s: rules[s] for s in symbols},
        strategy_parameters_by_symbol={s: parameters[s] for s in symbols},
        trade_policies_by_symbol={s: policies[s] for s in symbols},
        symbols=symbols,
        core_symbols=CORE_SYMBOLS,
        satellite_symbols=satellites,
        router_config=RouterConfig(
            filler_horizon_hours=24,
            hysteresis_atr=D("0"),
            satellite_budget_fraction_of_c=tranche / max_capital,
        ),
        strategy_semantics_by_symbol={s: semantics[s] for s in symbols},
        strict_core_idle_mask=bool(satellites),
        soft_filler_exit_enabled=True,
        soft_filler_exit_symbols=frozenset(
            s for s in satellites if horizons.get(s)
        ),
        entry_filter_by_symbol={
            s: filters[s] for s in satellites if s in filters
        },
        atr_reentry_level_by_symbol={
            s: reentry[s] for s in satellites if s in reentry
        },
        filler_horizon_hours_by_symbol={
            s: horizons[s] for s in satellites if s in horizons
        },
        core_allocation_policy=layout.policy,
    )
    row = _metrics(result, events)
    row.update(
        {
            "slots": layout.slots,
            "policy": layout.policy,
            "slot_notional_usdc": str(tranche),
            "reserve_usdc": str(reserve),
        }
    )
    return row


def _delta(integrated: dict[str, object], core: dict[str, object]) -> dict[str, object]:
    return {
        "net_pnl": str(D(str(integrated["net_pnl"])) - D(str(core["net_pnl"]))),
        "ending_equity": str(
            D(str(integrated["ending_equity"])) - D(str(core["ending_equity"]))
        ),
        "max_drawdown_pct": str(
            D(str(integrated["max_drawdown_pct"]))
            - D(str(core["max_drawdown_pct"]))
        ),
        "completed_trades": (
            int(integrated["completed_trades"]) - int(core["completed_trades"])
        ),
        "zero_slot_hours_reduced": str(
            D(str(core["zero_slot_hours"]))
            - D(str(integrated["zero_slot_hours"]))
        ),
        "slot_utilization_pct_gain": str(
            D(str(integrated["slot_utilization_pct"]))
            - D(str(core["slot_utilization_pct"]))
        ),
    }


def main() -> None:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client)
    report_start, report_end, candles, provenance = _histories(client)

    evidence: dict[str, object] = {
        "schema_version": 1,
        "purpose": "CONTROLLED_SLOT_LAYOUT_RESEARCH",
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "frozen_profiles": True,
        "core_priority": True,
        "no_leverage": True,
        "orders_sent": False,
        "paper_state_modified": False,
        "layouts": [
            {"name": layout.name, "slots": layout.slots, "policy": layout.policy}
            for layout in LAYOUTS
        ],
        "universes": {
            key: list(CORE_SYMBOLS + satellites)
            for key, satellites in UNIVERSES.items()
        },
        "capital_results": {},
        "provenance": provenance,
    }

    for capital in (D("250"), D("1000")):
        cap_rows: dict[str, object] = {}
        for cost_name, costs in (("baseline", BASELINE_COSTS), ("stress", STRESS_COSTS)):
            core_rows: dict[str, object] = {}
            for layout in LAYOUTS:
                core_rows[layout.name] = _run(
                    max_capital=capital,
                    layout=layout,
                    satellites=(),
                    costs=costs,
                    candles=candles,
                    rules=rules,
                    report_start=report_start,
                    report_end=report_end,
                )

            universe_rows: dict[str, object] = {"CORE10": core_rows}
            for universe_name in ("VALIDATED12", "ALL15"):
                satellites = UNIVERSES[universe_name]
                rows: dict[str, object] = {}
                for layout in LAYOUTS:
                    integrated = _run(
                        max_capital=capital,
                        layout=layout,
                        satellites=satellites,
                        costs=costs,
                        candles=candles,
                        rules=rules,
                        report_start=report_start,
                        report_end=report_end,
                    )
                    rows[layout.name] = {
                        **integrated,
                        "delta_vs_core_same_layout": _delta(
                            integrated, core_rows[layout.name]
                        ),
                    }
                universe_rows[universe_name] = rows
            cap_rows[cost_name] = universe_rows
        evidence["capital_results"][str(capital)] = cap_rows

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()

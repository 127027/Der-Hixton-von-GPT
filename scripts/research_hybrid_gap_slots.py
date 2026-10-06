"""Hybrid Core/Satellite capital geometry research.

Core stays frozen at two equal ranked-repeat tranches. Only the completely-idle
Satellite mode changes from 2 to 5 independent one-position fillers.
"""

from __future__ import annotations

import json
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from validate_15coin_satellite_integration import _histories, _maps, _rules

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.satellite_portfolio import RouterConfig, run_filler_router_portfolio
from hixton.data.binance import BinancePublicClient
from hixton.domain.allocation import RANKED_REPEAT
from hixton.domain.capital import capital_plan
from hixton.domain.satellite_layer import (
    ACTIVE_SHARED_SATELLITES,
    CORE_SYMBOLS,
    SATELLITE_SYMBOLS,
)

D = Decimal
CENT = D("0.01")
OUTPUT = Path("evidence/hybrid-gap-slot-matrix.json")
SATELLITE_COUNTS = (2, 3, 4, 5)


def _sat_notional(capital: D, count: int) -> tuple[D, D]:
    value = (capital / D(count)).quantize(CENT, rounding=ROUND_DOWN)
    return value, capital - value * D(count)


def _exposure(result, capital: D) -> dict[str, object]:
    total_hours = D(
        str((result.report_end_utc - result.report_start_utc).total_seconds() / 3600)
    )
    capital_hours = sum(
        (
            trade.entry_quote_spend / capital * trade.holding_hours
            for trade in result.trades
        ),
        D("0"),
    )
    return {
        "capital_exposure_hours_equivalent": str(capital_hours),
        "capital_utilization_pct": str(
            capital_hours / total_hours * D("100") if total_hours else D("0")
        ),
    }


def _run(
    *,
    capital: D,
    satellites: tuple[str, ...],
    satellite_count: int,
    costs,
    candles,
    rules,
    report_start,
    report_end,
):
    parameters, policies, semantics, filters, horizons, reentry = _maps()
    core_plan = capital_plan(capital)
    sat_notional, reserve = _sat_notional(capital, satellite_count)
    symbols = CORE_SYMBOLS + satellites
    result, events = run_filler_router_portfolio(
        candles_by_symbol={s: candles[s] for s in symbols},
        report_start_utc=report_start,
        report_end_utc=report_end,
        starting_cash=capital,
        target_notional=core_plan.target_notional_usdc,
        slot_count=core_plan.slot_count,
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
            satellite_budget_fraction_of_c=sat_notional / capital,
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
            s: horizons[s] for s in satellites if horizons.get(s)
        },
        core_allocation_policy=RANKED_REPEAT,
        satellite_position_limit=satellite_count,
        satellite_target_notional=sat_notional,
    )
    m = result.metrics
    zero_position_hours = sum(
        not point.active_position for point in result.equity_curve
    )
    per_symbol = {
        symbol: {
            "trades": sum(trade.symbol == symbol for trade in result.trades),
            "net_pnl": str(
                sum(
                    (
                        trade.realized_pnl
                        for trade in result.trades
                        if trade.symbol == symbol
                    ),
                    D("0"),
                )
            ),
        }
        for symbol in result.symbols
    }
    metrics = {
        "starting_equity": str(m.starting_equity),
        "ending_equity": str(m.ending_equity),
        "net_pnl": str(m.net_pnl),
        "return_pct": str(m.return_pct),
        "completed_trades": m.completed_trades,
        "completed_slot_trades": m.completed_slot_trades,
        "max_drawdown_pct": str(m.max_drawdown_pct),
        "zero_position_hours": str(zero_position_hours),
        "zero_position_pct": str(
            D(zero_position_hours) / D(len(result.equity_curve)) * D("100")
            if result.equity_curve
            else D("0")
        ),
        "max_concurrent_positions": result.max_concurrent_positions,
        "per_symbol": per_symbol,
    }
    metrics.update(_exposure(result, capital))
    metrics["core_slot_count"] = core_plan.slot_count
    metrics["core_slot_notional_usdc"] = str(core_plan.target_notional_usdc)
    metrics["satellite_position_limit"] = satellite_count
    metrics["satellite_notional_usdc"] = str(sat_notional)
    metrics["satellite_reserve_usdc"] = str(reserve)
    metrics["handoffs"] = sum(
        event.get("decision") == "STRICT_IDLE_HANDOFF" for event in events
    )
    metrics["satellite_trades"] = sum(
        trade.symbol in SATELLITE_SYMBOLS for trade in result.trades
    )
    metrics["satellite_pnl"] = str(
        sum(
            (
                trade.realized_pnl
                for trade in result.trades
                if trade.symbol in SATELLITE_SYMBOLS
            ),
            D("0"),
        )
    )
    metrics["per_satellite"] = {
        symbol: {
            "trades": sum(trade.symbol == symbol for trade in result.trades),
            "net_pnl": str(
                sum(
                    (
                        trade.realized_pnl
                        for trade in result.trades
                        if trade.symbol == symbol
                    ),
                    D("0"),
                )
            ),
        }
        for symbol in satellites
    }
    return metrics


def _delta(core: dict[str, object], mixed: dict[str, object]) -> dict[str, object]:
    return {
        "net_pnl": str(D(str(mixed["net_pnl"])) - D(str(core["net_pnl"]))),
        "ending_equity": str(
            D(str(mixed["ending_equity"])) - D(str(core["ending_equity"]))
        ),
        "max_drawdown_pct": str(
            D(str(mixed["max_drawdown_pct"])) - D(str(core["max_drawdown_pct"]))
        ),
        "completed_trades": int(mixed["completed_trades"]) - int(core["completed_trades"]),
        "zero_position_hours_reduced": str(
            D(str(core["zero_position_hours"]))
            - D(str(mixed["zero_position_hours"]))
        ),
        "capital_utilization_pct_gain": str(
            D(str(mixed["capital_utilization_pct"]))
            - D(str(core["capital_utilization_pct"]))
        ),
    }


def main() -> None:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client)
    report_start, report_end, candles, provenance = _histories(client)
    evidence: dict[str, object] = {
        "schema_version": 1,
        "purpose": "HYBRID_CORE2_SATELLITE_2_TO_5_GAP_LAYOUT",
        "core_geometry_frozen": {
            "slots": 2,
            "policy": RANKED_REPEAT,
            "rule": "max_capital / 2",
        },
        "satellite_counts": list(SATELLITE_COUNTS),
        "universes": {
            "VALIDATED": list(ACTIVE_SHARED_SATELLITES),
            "ALL_FIVE": list(SATELLITE_SYMBOLS),
        },
        "capital_results": {},
        "orders_sent": False,
        "paper_state_modified": False,
        "provenance": provenance,
    }
    for capital in (D("250"), D("1000")):
        capital_rows: dict[str, object] = {}
        for cost_name, costs in (("baseline", BASELINE_COSTS), ("stress", STRESS_COSTS)):
            core = _run(
                capital=capital,
                satellites=(),
                satellite_count=2,
                costs=costs,
                candles=candles,
                rules=rules,
                report_start=report_start,
                report_end=report_end,
            )
            universe_rows: dict[str, object] = {"CORE10": core}
            for universe_name, satellites in (
                ("VALIDATED", ACTIVE_SHARED_SATELLITES),
                ("ALL_FIVE", SATELLITE_SYMBOLS),
            ):
                rows = {}
                for count in SATELLITE_COUNTS:
                    mixed = _run(
                        capital=capital,
                        satellites=satellites,
                        satellite_count=count,
                        costs=costs,
                        candles=candles,
                        rules=rules,
                        report_start=report_start,
                        report_end=report_end,
                    )
                    rows[str(count)] = {
                        **mixed,
                        "delta_vs_core": _delta(core, mixed),
                    }
                universe_rows[universe_name] = rows
            capital_rows[cost_name] = universe_rows
        evidence["capital_results"][str(capital)] = capital_rows

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()

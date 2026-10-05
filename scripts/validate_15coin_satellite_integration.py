"""End-to-end validation for the 15-market Core+Satellite candidate.

Produces both:
1) isolated 15 x 250-USDC laboratory evidence; and
2) one shared 250-USDC / 2x125 portfolio with strict Core preemption.
No Paper/Live state is touched and no orders are sent.
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.satellite_portfolio import RouterConfig, run_filler_router_portfolio
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.capital import capital_plan
from hixton.domain.models import Candle
from hixton.domain.satellite_layer import (
    ALL_15_SYMBOLS,
    CORE_SYMBOLS,
    SATELLITE_PROFILES,
    SATELLITE_SYMBOLS,
)
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

D = Decimal
BAR_HOURS = 1
OUTPUT = Path("evidence/15coin-satellite-integration.json")
VERSION = "HIXTON-V6-SATELLITE-15-CANDIDATE-1"


def _rules(client: BinancePublicClient) -> dict[str, ExecutionRules]:
    result: dict[str, ExecutionRules] = {}
    for symbol in ALL_15_SYMBOLS:
        saved = client.symbol_rules(symbol)
        if not saved.tradable_for_quote("USDC"):
            raise RuntimeError(f"{symbol}: current USDC market is not tradable")
        result[symbol] = ExecutionRules(
            tick_size=saved.tick_size,
            step_size=saved.step_size,
            min_qty=saved.min_qty,
            min_notional=saved.min_notional,
        )
    return result


def _adapt(candles: list[Candle], target: str) -> list[Candle]:
    return [
        replace(
            candle,
            symbol=target,
            source="binance_spot_usdt_market_proxy_for_15coin_candidate",
        )
        for candle in candles
    ]


def _histories(client: BinancePublicClient):
    _warmup, report_start, report_end = safe_closed_window()
    warmup_start = report_start - V6_COIN_STRATEGY.parameters.warmup_bars * (
        report_end - report_end.replace(minute=0, second=0, microsecond=0)
    )
    # The expression above is zero on hourly boundaries; use explicit 400h instead.
    from datetime import timedelta
    warmup_start = report_start - timedelta(hours=400)
    candles: dict[str, list[Candle]] = {}
    provenance: dict[str, dict[str, str]] = {}

    for symbol in CORE_SYMBOLS:
        source = symbol.removesuffix("USDC") + "USDT"
        raw = client.fetch_klines(source, start=warmup_start, end_exclusive=report_end)
        adapted = _adapt(raw, symbol)
        audit_candles(
            adapted,
            expected_symbol=symbol,
            expected_start=warmup_start,
            expected_end_exclusive=report_end,
        ).require_valid()
        candles[symbol] = adapted
        provenance[symbol] = {"target": symbol, "history_proxy": source, "layer": "CORE"}

    for profile in SATELLITE_PROFILES:
        raw = client.fetch_klines(
            profile.history_proxy,
            start=warmup_start,
            end_exclusive=report_end,
        )
        adapted = _adapt(raw, profile.symbol)
        audit_candles(
            adapted,
            expected_symbol=profile.symbol,
            expected_start=warmup_start,
            expected_end_exclusive=report_end,
        ).require_valid()
        candles[profile.symbol] = adapted
        provenance[profile.symbol] = {
            "target": profile.symbol,
            "history_proxy": profile.history_proxy,
            "layer": "SATELLITE",
        }
    return report_start, report_end, candles, provenance


def _maps():
    parameters = {p.symbol: p.parameters for p in V6_COIN_STRATEGY.coin_profiles}
    policies = {p.symbol: p.trade_policy for p in V6_COIN_STRATEGY.coin_profiles}
    semantics = dict.fromkeys(CORE_SYMBOLS, V6_COIN_STRATEGY.semantics)
    entry_filters = {}
    horizons = {}
    reentry = {}
    for profile in SATELLITE_PROFILES:
        parameters[profile.symbol] = profile.parameters
        policies[profile.symbol] = profile.trade_policy
        semantics[profile.symbol] = profile.semantics
        entry_filters[profile.symbol] = profile.entry_block_reason
        if profile.horizon_hours:
            horizons[profile.symbol] = profile.horizon_hours
        if profile.reentry_atr_level is not None:
            reentry[profile.symbol] = profile.reentry_atr_level
    return parameters, policies, semantics, entry_filters, horizons, reentry


def _run(
    *,
    symbols: tuple[str, ...],
    core_symbols: tuple[str, ...],
    satellite_symbols: tuple[str, ...],
    candles: dict[str, list[Candle]],
    rules: dict[str, ExecutionRules],
    report_start,
    report_end,
    costs,
    starting_cash: D,
    target_notional: D,
    slot_count: int,
):
    parameters, policies, semantics, filters, horizons, reentry = _maps()
    result, events = run_filler_router_portfolio(
        candles_by_symbol={s: candles[s] for s in symbols},
        report_start_utc=report_start,
        report_end_utc=report_end,
        starting_cash=starting_cash,
        target_notional=target_notional,
        slot_count=slot_count,
        costs=costs,
        execution_rules={s: rules[s] for s in symbols},
        strategy_parameters_by_symbol={s: parameters[s] for s in symbols},
        trade_policies_by_symbol={s: policies[s] for s in symbols},
        symbols=symbols,
        core_symbols=core_symbols,
        satellite_symbols=satellite_symbols,
        router_config=RouterConfig(
            filler_horizon_hours=24,
            hysteresis_atr=D("0"),
            satellite_budget_fraction_of_c=D("0.50") if slot_count == 2 else D("1"),
        ),
        strategy_semantics_by_symbol={s: semantics[s] for s in symbols},
        strict_core_idle_mask=bool(core_symbols and satellite_symbols),
        soft_filler_exit_enabled=True,
        soft_filler_exit_symbols=frozenset(
            s for s in satellite_symbols if horizons.get(s)
        ),
        entry_filter_by_symbol={
            s: filters[s] for s in satellite_symbols if s in filters
        },
        atr_reentry_level_by_symbol={
            s: reentry[s] for s in satellite_symbols if s in reentry
        },
        filler_horizon_hours_by_symbol={
            s: horizons[s] for s in satellite_symbols if s in horizons
        },
    )
    return result, events


def _metrics(result):
    m = result.metrics
    per_symbol = {}
    for symbol in result.symbols:
        trades = [t for t in result.trades if t.symbol == symbol]
        per_symbol[symbol] = {
            "net_pnl": str(sum((t.realized_pnl for t in trades), D("0"))),
            "completed_trades": len(trades),
            "slot_trades": sum(t.slot_count for t in trades),
        }
    return {
        "starting_equity": str(m.starting_equity),
        "ending_equity": str(m.ending_equity),
        "net_pnl": str(m.net_pnl),
        "return_pct": str(m.return_pct),
        "completed_trades": m.completed_trades,
        "completed_slot_trades": m.completed_slot_trades,
        "max_drawdown_pct": str(m.max_drawdown_pct),
        "max_concurrent_slots": result.max_concurrent_positions,
        "per_symbol": per_symbol,
    }


def _isolated(costs, candles, rules, report_start, report_end):
    rows = {}
    total_start = D("0")
    total_end = D("0")
    total_trades = 0
    for symbol in ALL_15_SYMBOLS:
        sat = (symbol,) if symbol in SATELLITE_SYMBOLS else ()
        core = (symbol,) if symbol in CORE_SYMBOLS else ()
        result, _events = _run(
            symbols=(symbol,),
            core_symbols=core,
            satellite_symbols=sat,
            candles=candles,
            rules=rules,
            report_start=report_start,
            report_end=report_end,
            costs=costs,
            starting_cash=D("250"),
            target_notional=D("250"),
            slot_count=1,
        )
        row = _metrics(result)
        rows[symbol] = row
        total_start += D(row["starting_equity"])
        total_end += D(row["ending_equity"])
        total_trades += int(row["completed_trades"])
    return {
        "starting_equity": str(total_start),
        "ending_equity": str(total_end),
        "net_pnl": str(total_end - total_start),
        "return_pct": str((total_end / total_start - D("1")) * D("100")),
        "completed_trades": total_trades,
        "per_symbol": rows,
    }


def _shared(costs, candles, rules, report_start, report_end, include_satellites: bool):
    plan = capital_plan(D("250"))
    symbols = ALL_15_SYMBOLS if include_satellites else CORE_SYMBOLS
    sats = SATELLITE_SYMBOLS if include_satellites else ()
    result, events = _run(
        symbols=symbols,
        core_symbols=CORE_SYMBOLS,
        satellite_symbols=sats,
        candles=candles,
        rules=rules,
        report_start=report_start,
        report_end=report_end,
        costs=costs,
        starting_cash=D("250"),
        target_notional=plan.target_notional_usdc,
        slot_count=plan.slot_count,
    )
    metrics = _metrics(result)
    metrics["strict_idle_handoffs"] = sum(
        event.get("decision") == "STRICT_IDLE_HANDOFF" for event in events
    )
    metrics["satellite_cycles"] = sum(t.symbol in SATELLITE_SYMBOLS for t in result.trades)
    metrics["core_cycles"] = sum(t.symbol in CORE_SYMBOLS for t in result.trades)
    metrics["satellite_realized_pnl"] = str(sum(
        (t.realized_pnl for t in result.trades if t.symbol in SATELLITE_SYMBOLS), D("0")
    ))
    metrics["core_realized_pnl"] = str(sum(
        (t.realized_pnl for t in result.trades if t.symbol in CORE_SYMBOLS), D("0")
    ))
    metrics["two_slot_core_cycles"] = sum(
        t.symbol in CORE_SYMBOLS and t.slot_count == 2 for t in result.trades
    )
    metrics["satellite_multi_slot_cycles"] = sum(
        t.symbol in SATELLITE_SYMBOLS and t.slot_count != 1 for t in result.trades
    )
    if result.max_concurrent_positions > 2:
        raise RuntimeError("candidate exceeded two shared 125-USDC slots")
    if metrics["satellite_multi_slot_cycles"]:
        raise RuntimeError("a Satellite consumed more than one 125-USDC slot")
    return metrics


def main() -> None:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client)
    report_start, report_end, candles, provenance = _histories(client)

    evidence = {
        "schema_version": 1,
        "candidate": VERSION,
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "capital_contract": {
            "shared_max_usdc": "250",
            "slot_count": 2,
            "slot_notional_usdc": "125",
            "satellite_max_slots_per_symbol": 1,
            "core_ranked_repeat": True,
            "core_preempts_satellites_next_open": True,
        },
        "symbols": {
            "core": list(CORE_SYMBOLS),
            "satellites": list(SATELLITE_SYMBOLS),
            "all_15": list(ALL_15_SYMBOLS),
        },
        "provenance": provenance,
        "baseline": {},
        "stress": {},
        "orders_sent": False,
        "paper_state_modified": False,
    }
    for costs, key in ((BASELINE_COSTS, "baseline"), (STRESS_COSTS, "stress")):
        isolated = _isolated(costs, candles, rules, report_start, report_end)
        core_only = _shared(costs, candles, rules, report_start, report_end, False)
        integrated = _shared(costs, candles, rules, report_start, report_end, True)
        evidence[key] = {
            "isolated_15x250": isolated,
            "shared_250_core_only": core_only,
            "shared_250_core_plus_satellites": integrated,
            "shared_delta": {
                "ending_equity": str(
                    D(integrated["ending_equity"]) - D(core_only["ending_equity"])
                ),
                "net_pnl": str(D(integrated["net_pnl"]) - D(core_only["net_pnl"])),
                "completed_trades": (
                    int(integrated["completed_trades"])
                    - int(core_only["completed_trades"])
                ),
                "max_drawdown_pct": str(
                    D(integrated["max_drawdown_pct"]) - D(core_only["max_drawdown_pct"])
                ),
            },
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()

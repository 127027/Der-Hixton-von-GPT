"""Clean Satellite V1 baseline census for SUI/NEAR/UNI/AAVE/BCH.

Research-only. This deliberately ignores the old frozen V6-derived Satellite profiles.
It runs the original Hixton V1 / DMS_V1 semantics unchanged first, so later work can
improve each Satellite from a neutral common baseline instead of copying Core V6
profiles onto different markets.

The three-year diagnostic uses the checkpoint's full-history USDT proxy for each asset
and maps candles to the USDC market identity. A direct-USDC one-year holdout is also
reported as rejection-only evidence. No parameter selection occurs here.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, BacktestResult, ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import Candle
from hixton.domain.versions import V1_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

D = Decimal
BAR = timedelta(hours=1)
REAL_USDC_HOLDOUT = timedelta(days=365)
SATELLITES = ("SUIUSDC", "NEARUSDC", "UNIUSDC", "AAVEUSDC", "BCHUSDC")
CHECKPOINT = Path("agent_memory/autonomy/satellite_step4_checkpoint.json")
OUTPUT = Path("evidence/satellite-v1-baseline.json")
REFERENCE_CAPITAL = D("250")
OWNER_TARGET_IDLE_FILL_PCT = D("90")


def _rules(client: BinancePublicClient, symbol: str) -> ExecutionRules:
    saved = client.symbol_rules(symbol)
    if not saved.tradable_for_quote("USDC"):
        raise RuntimeError(f"{symbol}: current Binance USDC rules are not tradable")
    return ExecutionRules(
        tick_size=saved.tick_size,
        step_size=saved.step_size,
        min_qty=saved.min_qty,
        min_notional=saved.min_notional,
    )


def _adapt(candles: list[Candle], target_symbol: str) -> list[Candle]:
    return [
        replace(
            candle,
            symbol=target_symbol,
            source="binance_spot_usdt_proxy_for_satellite_v1_baseline",
        )
        for candle in candles
    ]


def _run(
    *,
    symbol: str,
    candles: list[Candle],
    rules: ExecutionRules,
    start,
    end,
    costs: Any,
) -> BacktestResult:
    return run_single_backtest(
        symbol=symbol,
        candles=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=REFERENCE_CAPITAL,
        target_notional=REFERENCE_CAPITAL,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=V1_STRATEGY.parameters,
        strategy_semantics=V1_STRATEGY.semantics,
        strategy_version=V1_STRATEGY.version,
        trade_policy=None,
    )


def _summary(result: BacktestResult) -> dict[str, object]:
    trades = list(result.trades)
    holding = [float(t.holding_hours) for t in trades]
    total_position_hours = sum((t.holding_hours for t in trades), D("0"))
    report_hours = D(str((result.report_end_utc - result.report_start_utc).total_seconds() / 3600))
    active_hours = sum(1 for point in result.equity_curve if point.active_position)
    completed = result.metrics.completed_trades
    days = report_hours / D("24")
    return {
        "ending_equity": str(result.metrics.ending_equity),
        "net_pnl": str(result.metrics.net_pnl),
        "return_pct": str(result.metrics.return_pct),
        "completed_trades": completed,
        "trades_per_calendar_day": str(D(completed) / days) if days > 0 else None,
        "winning_trades": result.metrics.winning_trades,
        "losing_trades": result.metrics.losing_trades,
        "win_rate_pct": None if result.metrics.win_rate_pct is None else str(result.metrics.win_rate_pct),
        "profit_factor": None if result.metrics.profit_factor is None else str(result.metrics.profit_factor),
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "average_holding_hours": (
            None if result.metrics.average_holding_hours is None else str(result.metrics.average_holding_hours)
        ),
        "median_holding_hours": None if not holding else str(statistics.median(holding)),
        "max_holding_hours": None if not holding else str(max(holding)),
        "total_position_hours": str(total_position_hours),
        "active_calendar_hours": active_hours,
        "active_calendar_pct": str(D(active_hours) / D(len(result.equity_curve)) * D("100")),
        "profit_per_position_hour": (
            None if total_position_hours <= 0 else str(result.metrics.net_pnl / total_position_hours)
        ),
        "entry_signal_count": sum(1 for s in result.signals if s.action.value == "ENTER_LONG"),
        "exit_signal_count": sum(1 for s in result.signals if s.action.value == "EXIT_LONG"),
        "blocked_signal_count": len(result.blocked_signals),
        "open_position_at_end": result.open_position_at_end,
        "data_snapshot_sha256": result.data_snapshot_sha256,
    }


def _union_coverage(results: dict[str, BacktestResult]) -> dict[str, object]:
    rows = [list(results[s].equity_curve) for s in SATELLITES]
    lengths = {len(row) for row in rows}
    if len(lengths) != 1:
        raise RuntimeError(f"satellite V1 curves differ in length: {sorted(lengths)}")
    total = lengths.pop()
    active_any = 0
    active_counts: list[int] = []
    for points in zip(*rows, strict=True):
        timestamps = {p.time_utc for p in points}
        if len(timestamps) != 1:
            raise RuntimeError("satellite V1 curves are not time-aligned")
        count = sum(1 for p in points if p.active_position)
        active_counts.append(count)
        if count:
            active_any += 1
    coverage = D(active_any) / D(total) * D("100") if total else D("0")
    return {
        "calendar_hours": total,
        "hours_with_at_least_one_v1_satellite_active": active_any,
        "potential_union_active_pct": str(coverage),
        "owner_target_core_idle_fill_pct": str(OWNER_TARGET_IDLE_FILL_PCT),
        "gap_to_owner_target_pct_points": str(OWNER_TARGET_IDLE_FILL_PCT - coverage),
        "average_simultaneously_active_satellites": (
            str(D(sum(active_counts)) / D(total)) if total else "0"
        ),
        "interpretation": (
            "This is potential V1 Satellite availability across the full calendar, not yet the "
            "final shared-250-USDC realized fill of Core-idle hours. The next research stage must "
            "intersect Satellite opportunity windows with the protected Core idle mask."
        ),
    }


def main() -> None:
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    old_profiles = checkpoint.get("profiles", {})
    if set(SATELLITES) - set(old_profiles):
        raise RuntimeError("Step-4 checkpoint does not contain all five selected Satellite markets")

    _, report_start, report_end = safe_closed_window()
    warmup = V1_STRATEGY.parameters.warmup_bars
    warmup_start = report_start - warmup * BAR
    holdout_start = report_end - REAL_USDC_HOLDOUT
    holdout_warmup_start = holdout_start - warmup * BAR

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol: dict[str, object] = {}
    proxy_baseline_results: dict[str, BacktestResult] = {}

    for symbol in SATELLITES:
        source = str(old_profiles[symbol]["history_source_for_training"])
        rules = _rules(client, symbol)

        proxy = _adapt(
            client.fetch_klines(source, start=warmup_start, end_exclusive=report_end),
            symbol,
        )
        audit_candles(
            proxy,
            expected_symbol=symbol,
            expected_start=warmup_start,
            expected_end_exclusive=report_end,
        ).require_valid()

        direct = client.fetch_klines(
            symbol,
            start=holdout_warmup_start,
            end_exclusive=report_end,
        )
        audit_candles(
            direct,
            expected_symbol=symbol,
            expected_start=holdout_warmup_start,
            expected_end_exclusive=report_end,
        ).require_valid()

        proxy_base = _run(
            symbol=symbol,
            candles=proxy,
            rules=rules,
            start=report_start,
            end=report_end,
            costs=BASELINE_COSTS,
        )
        proxy_stress = _run(
            symbol=symbol,
            candles=proxy,
            rules=rules,
            start=report_start,
            end=report_end,
            costs=STRESS_COSTS,
        )
        direct_base = _run(
            symbol=symbol,
            candles=direct,
            rules=rules,
            start=holdout_start,
            end=report_end,
            costs=BASELINE_COSTS,
        )
        direct_stress = _run(
            symbol=symbol,
            candles=direct,
            rules=rules,
            start=holdout_start,
            end=report_end,
            costs=STRESS_COSTS,
        )
        proxy_baseline_results[symbol] = proxy_base

        per_symbol[symbol] = {
            "basis": "ORIGINAL_HIXTON_V1_DMS_V1_UNCHANGED",
            "proxy_symbol": source,
            "v1_parameters": asdict(V1_STRATEGY.parameters),
            "v1_semantics": V1_STRATEGY.semantics.value,
            "three_year_proxy": {
                "baseline": _summary(proxy_base),
                "stress": _summary(proxy_stress),
            },
            "real_usdc_one_year_rejection_only": {
                "baseline": _summary(direct_base),
                "stress": _summary(direct_stress),
            },
        }

    evidence = {
        "schema_version": 1,
        "study": "SATELLITE_V1_CLEAN_BASELINE",
        "research_only": True,
        "activation_performed": False,
        "product_mutated": False,
        "protected_core_role": "PRIMARY_ENGINE_UNCHANGED",
        "satellite_role": "FILL_PROTECTED_CORE_IDLE_TIME",
        "owner_observation": {
            "core_active_fraction_approx": "0.10",
            "core_idle_fraction_approx": "0.90",
            "satellite_goal": "Use five independently developed Satellite strategies to monetize as much of the ~90% Core-idle time as possible without reducing protected Core performance.",
        },
        "reference_account_usdc": str(REFERENCE_CAPITAL),
        "capital_semantics": (
            "Each per-symbol V1 run is an isolated diagnostic using full C=250. The final five-market "
            "Satellite layer must later use one shared C=250 account and may only deploy capital that "
            "does not harm protected Core opportunities."
        ),
        "strategy_contract": {
            "starting_point": "V1_STRATEGY",
            "semantics": V1_STRATEGY.semantics.value,
            "parameters": asdict(V1_STRATEGY.parameters),
            "v6_core_templates_used": False,
            "parameter_selection_performed": False,
            "old_step4_profiles_are_baseline_inputs": False,
            "old_step4_profiles_used_only_for_history_source_lookup": True,
        },
        "window": {
            "three_year_start_utc": report_start.isoformat(),
            "end_utc": report_end.isoformat(),
            "real_usdc_holdout_start_utc": holdout_start.isoformat(),
        },
        "satellites": list(SATELLITES),
        "per_symbol": per_symbol,
        "five_market_potential_coverage": _union_coverage(proxy_baseline_results),
        "next_stage": {
            "id": "SATELLITE_V1_PER_MARKET_DIAGNOSIS",
            "rule": (
                "Diagnose each market separately from V1 baseline evidence: entry lateness/noise, exit "
                "lateness, holding duration, signal scarcity, false breakouts, cost sensitivity and "
                "profit-per-hour. Only then evolve a dedicated Satellite-V1 profile per market on "
                "training evidence. Do not borrow Core V6 profiles as defaults."
            ),
            "final_validation_requirement": (
                "After per-market development, replay the five together against the exact protected "
                "10-Core idle mask in one shared 250-USDC account. Success means higher after-cost "
                "shared equity and materially higher Core-idle utilization without Core regression."
            ),
        },
        "safety": {
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "future_outcomes_used_for_decisions": False,
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "study": evidence["study"],
        "satellites": evidence["satellites"],
        "potential_union_active_pct": evidence["five_market_potential_coverage"]["potential_union_active_pct"],
        "target_idle_fill_pct": evidence["five_market_potential_coverage"]["owner_target_core_idle_fill_pct"],
        "next_stage": evidence["next_stage"]["id"],
    }, indent=2))


if __name__ == "__main__":
    main()

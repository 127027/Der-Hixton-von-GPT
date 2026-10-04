"""Continuous isolated 5x250 Satellite policy refinement.

Purpose:
- keep ALL five primary Satellites active until mature or explicitly replaced;
- do not treat a merely positive but weak profile as final;
- use Run #90 TRAINING-selected parameter seeds only;
- search a materially different point-in-time trade-policy family per market;
- select on two independent TRAINING years under STRESS only;
- Direct-USDC validation/full-window may reject, never choose the next search direction.

This is research-only. The protected ten-Core product is untouched.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V1_STRATEGY
from scripts.satellite_v1_evolution_research import SATELLITES, _adapt, _metrics, _rules

D = Decimal
BAR = timedelta(hours=1)
MISSION = Path("agent_memory/autonomy/current_mission.json")
SOURCES = Path("agent_memory/autonomy/satellite_v1_idle_horizon_sources.json")
SEEDS = Path("agent_memory/autonomy/satellite_refinement_seeds.json")
OUTPUT = Path("evidence/satellite-isolated-5x250-policy-refinement.json")
CAPITAL = D("250")
MIN_MATURE_CYCLES = 157


def _canonical_window() -> tuple[datetime, datetime]:
    mission = json.loads(MISSION.read_text(encoding="utf-8"))
    baseline = mission.get("canonical_core_baseline") or {}
    start = datetime.fromisoformat(str(baseline["report_start_utc"])).astimezone(timezone.utc)
    end = datetime.fromisoformat(str(baseline["report_end_utc"])).astimezone(timezone.utc)
    return start, end


def _run(
    *,
    symbol: str,
    candles,
    rules,
    start,
    end,
    costs,
    params: StrategyParameters,
    policy: TradePolicy,
    version: str,
):
    return run_single_backtest(
        symbol=symbol,
        candles=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=CAPITAL,
        target_notional=CAPITAL,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=params,
        strategy_semantics=V1_STRATEGY.semantics,
        strategy_version=version,
        trade_policy=policy,
    )


def _policies() -> list[tuple[str, TradePolicy]]:
    rows: list[tuple[str, TradePolicy]] = [("BASE", TradePolicy())]
    for cmo in (0.10, 0.20, 0.30, 0.40):
        rows.append((f"CMO_{int(cmo*100):02d}", TradePolicy(cmo_floor=cmo)))
        rows.append((f"CMO_{int(cmo*100):02d}_S24", TradePolicy(cmo_floor=cmo, slope_bars=24)))
    for cmo in (0.20, 0.30):
        rows.append((f"CMO_{int(cmo*100):02d}_S72", TradePolicy(cmo_floor=cmo, slope_bars=72)))
    for stop in (1.0, 1.5, 2.0):
        rows.append((f"STOP_{stop}", TradePolicy(stop_atr=stop)))
    for trail in (1.0, 1.5, 2.0):
        rows.append((f"TRAIL_{trail}", TradePolicy(trail_atr=trail)))
    for cmo in (0.20, 0.30):
        for slope in (24, 72):
            rows.append((
                f"CMO_{int(cmo*100):02d}_S{slope}_TRAIL_1.5",
                TradePolicy(cmo_floor=cmo, slope_bars=slope, trail_atr=1.5),
            ))
            rows.append((
                f"CMO_{int(cmo*100):02d}_S{slope}_STOP_1.5",
                TradePolicy(cmo_floor=cmo, slope_bars=slope, stop_atr=1.5),
            ))
    return rows


def _train_score(a, b) -> tuple[D, D, D, int, D]:
    pa = D(str(a.metrics.net_pnl))
    pb = D(str(b.metrics.net_pnl))
    dd = max(D(str(a.metrics.max_drawdown_pct)), D(str(b.metrics.max_drawdown_pct)))
    trades = min(a.metrics.completed_trades, b.metrics.completed_trades)
    hours = D("0")
    pnl = D("0")
    for result in (a, b):
        hours += sum((t.holding_hours for t in result.trades), D("0"))
        pnl += result.metrics.net_pnl
    pph = pnl / hours if hours > 0 else D("-999")
    return (min(pa, pb), pa + pb, -dd, trades, pph)


def _positive(result) -> bool:
    return result.metrics.net_pnl > 0 and result.metrics.completed_trades > 0


def main() -> None:
    start, end = _canonical_window()
    train_a_end = start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    validation_start = train_b_end

    source_doc = json.loads(SOURCES.read_text(encoding="utf-8"))
    source_rows = source_doc["per_symbol"]
    seed_doc = json.loads(SEEDS.read_text(encoding="utf-8"))
    seed_rows = seed_doc["per_symbol"]
    if tuple(seed_rows) != SATELLITES:
        raise RuntimeError(f"seed order drifted: {tuple(seed_rows)!r}")

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    policy_grid = _policies()
    per_symbol: dict[str, object] = {}
    mature: list[str] = []
    profitability_pass: list[str] = []

    for symbol in SATELLITES:
        params = StrategyParameters(**seed_rows[symbol]["parameters"])
        rules = _rules(client, symbol)
        proxy_symbol = str(source_rows[symbol]["history_source_for_training"])
        warmup = params.warmup_bars

        proxy = _adapt(
            client.fetch_klines(
                proxy_symbol,
                start=start - warmup * BAR,
                end_exclusive=end,
            ),
            symbol,
        )
        audit_candles(
            proxy,
            expected_symbol=symbol,
            expected_start=start - warmup * BAR,
            expected_end_exclusive=end,
        ).require_valid()

        direct = client.fetch_klines(
            symbol,
            start=validation_start - warmup * BAR,
            end_exclusive=end,
        )
        audit_candles(
            direct,
            expected_symbol=symbol,
            expected_start=validation_start - warmup * BAR,
            expected_end_exclusive=end,
        ).require_valid()

        training_rows = []
        ranked = []
        for name, policy in policy_grid:
            version = f"HIXTON-V5-SAT-POLICY-{symbol}-{name}"
            ta = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=start, end=train_a_end, costs=STRESS_COSTS,
                params=params, policy=policy, version=version,
            )
            tb = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=train_a_end, end=train_b_end, costs=STRESS_COSTS,
                params=params, policy=policy, version=version,
            )
            row = {
                "name": name,
                "policy": asdict(policy),
                "train_a_stress": _metrics(ta),
                "train_b_stress": _metrics(tb),
                "training_both_positive": _positive(ta) and _positive(tb),
                "score": [str(x) for x in _train_score(ta, tb)],
            }
            training_rows.append(row)
            if row["training_both_positive"]:
                ranked.append((_train_score(ta, tb), name, policy, row))

        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            per_symbol[symbol] = {
                "seed_parameters": asdict(params),
                "prior_status": seed_rows[symbol]["prior_status"],
                "training_candidates": training_rows,
                "training_winner": None,
                "validation": None,
                "profitability_pass": False,
                "maturity_pass": False,
                "next_reason": "NO_POLICY_WITH_POSITIVE_STRESS_PNL_IN_BOTH_TRAINING_YEARS",
            }
            continue

        _, winner_name, winner_policy, winner_training = ranked[0]
        version = f"HIXTON-V5-SAT-POLICY-FROZEN-{symbol}-{winner_name}"
        v_base = _run(
            symbol=symbol, candles=direct, rules=rules,
            start=validation_start, end=end, costs=BASELINE_COSTS,
            params=params, policy=winner_policy, version=version,
        )
        v_stress = _run(
            symbol=symbol, candles=direct, rules=rules,
            start=validation_start, end=end, costs=STRESS_COSTS,
            params=params, policy=winner_policy, version=version,
        )
        f_base = _run(
            symbol=symbol, candles=proxy, rules=rules,
            start=start, end=end, costs=BASELINE_COSTS,
            params=params, policy=winner_policy, version=version,
        )
        f_stress = _run(
            symbol=symbol, candles=proxy, rules=rules,
            start=start, end=end, costs=STRESS_COSTS,
            params=params, policy=winner_policy, version=version,
        )

        profit_ok = all(_positive(x) for x in (v_base, v_stress, f_base, f_stress))
        mature_ok = profit_ok and f_stress.metrics.completed_trades >= MIN_MATURE_CYCLES
        if profit_ok:
            profitability_pass.append(symbol)
        if mature_ok:
            mature.append(symbol)

        per_symbol[symbol] = {
            "seed_parameters": asdict(params),
            "prior_status": seed_rows[symbol]["prior_status"],
            "training_candidates": training_rows,
            "training_winner": {
                "name": winner_name,
                "policy": asdict(winner_policy),
                "training": winner_training,
            },
            "validation": {
                "baseline": _metrics(v_base),
                "stress": _metrics(v_stress),
                "full_3y_proxy_baseline": _metrics(f_base),
                "full_3y_proxy_stress": _metrics(f_stress),
            },
            "profitability_pass": profit_ok,
            "maturity_pass": mature_ok,
            "maturity_gap": (
                None if mature_ok else {
                    "full_3y_stress_completed_trades": f_stress.metrics.completed_trades,
                    "target_completed_trades": MIN_MATURE_CYCLES,
                    "positive_all_windows": profit_ok,
                }
            ),
            "next_reason": (
                "MATURE"
                if mature_ok else
                "PROFITABLE_BUT_NOT_FREQUENT_ENOUGH_CONTINUE"
                if profit_ok else
                "DIRECT_USDC_OR_FULL_STRESS_REJECTION_CONTINUE"
            ),
        }

    result = {
        "schema_version": 1,
        "study": "SATELLITE_ISOLATED_5X250_POLICY_REFINEMENT",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": seed_doc["protected_product_sha"],
        "capital_per_market_usdc": "250",
        "all_five_remain_active": True,
        "policy_family_count": len(policy_grid),
        "per_symbol": per_symbol,
        "profitability_pass_symbols": profitability_pass,
        "mature_symbols": mature,
        "mature_count": len(mature),
        "target_count": 5,
        "next_stage": (
            "SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY"
            if len(mature) == 5
            else "SATELLITE_ISOLATED_5X250_CONTINUE"
        ),
        "selection_contract": {
            "training_only_selects_policy": True,
            "two_independent_training_years_stress_positive_required": True,
            "direct_usdc_validation_rejection_only": True,
            "validation_does_not_choose_next_policy": True,
            "positive_but_weak_is_not_final": True,
            "minimum_full_3y_completed_trades_target": MIN_MATURE_CYCLES,
        },
        "safety": {
            "protected_core_mutated": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "private_credentials_used": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "study": result["study"],
        "profitability_pass_symbols": profitability_pass,
        "mature_symbols": mature,
        "mature_count": len(mature),
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()

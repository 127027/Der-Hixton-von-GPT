"""Autonomous isolated 5x250 holding-time refinement for Satellite fillers.

This stage is intentionally bounded and repeatable across six distinct rounds.
Each round:
- keeps the Run #90 per-market strategy parameters frozen;
- starts from the previous round's TRAINING-selected TradePolicy;
- explores one materially different point-in-time holding/exit/filter family;
- selects only on two independent TRAINING years under STRESS costs;
- uses Direct-USDC validation and full-window evidence only as rejection/maturity gates.

The protected ten-Core product is never mutated here.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

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
SEEDS = Path("agent_memory/autonomy/satellite_holding_seeds.json")
CONTROL = Path("agent_memory/autonomy/satellite_holding_control.json")
OUTPUT = Path("evidence/satellite-isolated-5x250-holding-refinement.json")
CAPITAL = D("250")
MIN_MATURE_CYCLES = 157


def _canonical_window() -> tuple[datetime, datetime]:
    mission = json.loads(MISSION.read_text(encoding="utf-8"))
    baseline = mission.get("canonical_core_baseline") or {}
    start = datetime.fromisoformat(str(baseline["report_start_utc"])).astimezone(timezone.utc)
    end = datetime.fromisoformat(str(baseline["report_end_utc"])).astimezone(timezone.utc)
    return start, end


def _run(*, symbol, candles, rules, start, end, costs, params, policy, version):
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


def _positive(result) -> bool:
    return result.metrics.net_pnl > 0 and result.metrics.completed_trades > 0


def _position_hours(result) -> D:
    return sum((trade.holding_hours for trade in result.trades), D("0"))


def _score(a, b, policy: TradePolicy) -> tuple[D, D, int, D, int]:
    pa = D(str(a.metrics.net_pnl))
    pb = D(str(b.metrics.net_pnl))
    ha = _position_hours(a)
    hb = _position_hours(b)
    ppha = pa / ha if ha > 0 else D("-999")
    pphb = pb / hb if hb > 0 else D("-999")
    trades = min(a.metrics.completed_trades, b.metrics.completed_trades)
    max_hold = policy.max_hold_bars if policy.max_hold_bars else 100000
    return (min(pa, pb), min(ppha, pphb), trades, pa + pb, -max_hold)


def _clamp(value: float, lo: float, hi: float) -> float:
    return round(max(lo, min(hi, value)), 4)


def _nearby_holds(base: int) -> tuple[int, ...]:
    if base <= 0:
        return (24, 48, 72, 120)
    vals = {
        max(6, base // 2),
        max(6, base - 24),
        base,
        min(168, base + 24),
        min(168, max(base + 48, base * 2)),
    }
    return tuple(sorted(v for v in vals if 0 < v <= 168))


def _dedupe(rows: list[tuple[str, TradePolicy]]) -> list[tuple[str, TradePolicy]]:
    seen = set()
    out = []
    for name, policy in rows:
        key = (
            policy.cmo_floor,
            policy.slope_bars,
            policy.stop_atr,
            policy.trail_atr,
            policy.max_hold_bars,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append((name, policy))
    return out


def _variants(base: TradePolicy, round_no: int) -> list[tuple[str, TradePolicy]]:
    rows: list[tuple[str, TradePolicy]] = [("INCUMBENT", base)]

    if round_no == 1:
        for hold in (24, 48, 72, 120, 168):
            rows.append((f"HOLD_{hold}", TradePolicy(
                cmo_floor=base.cmo_floor, slope_bars=base.slope_bars,
                stop_atr=base.stop_atr, trail_atr=base.trail_atr,
                max_hold_bars=hold,
            )))
        for hold in (48, 72, 120):
            for stop in (1.0, 1.5, 2.0):
                rows.append((f"H{hold}_STOP_{stop}", TradePolicy(
                    cmo_floor=base.cmo_floor, slope_bars=base.slope_bars,
                    stop_atr=stop, trail_atr=0.0, max_hold_bars=hold,
                )))
            for trail in (1.0, 1.5, 2.0):
                rows.append((f"H{hold}_TRAIL_{trail}", TradePolicy(
                    cmo_floor=base.cmo_floor, slope_bars=base.slope_bars,
                    stop_atr=0.0, trail_atr=trail, max_hold_bars=hold,
                )))

    elif round_no == 2:
        for hold in (6, 12, 18, 24, 36, 48):
            rows.append((f"SHORT_HOLD_{hold}", TradePolicy(
                cmo_floor=base.cmo_floor, slope_bars=base.slope_bars,
                stop_atr=base.stop_atr, trail_atr=base.trail_atr,
                max_hold_bars=hold,
            )))
            for atr in (0.75, 1.0, 1.25):
                rows.append((f"H{hold}_STOP_{atr}", TradePolicy(
                    cmo_floor=base.cmo_floor, slope_bars=base.slope_bars,
                    stop_atr=atr, trail_atr=0.0, max_hold_bars=hold,
                )))
                rows.append((f"H{hold}_TRAIL_{atr}", TradePolicy(
                    cmo_floor=base.cmo_floor, slope_bars=base.slope_bars,
                    stop_atr=0.0, trail_atr=atr, max_hold_bars=hold,
                )))

    elif round_no == 3:
        holds = _nearby_holds(base.max_hold_bars)
        cmos = sorted({
            _clamp(base.cmo_floor + delta, 0.0, 0.65)
            for delta in (-0.10, -0.05, 0.0, 0.05, 0.10)
        })
        for cmo in cmos:
            for hold in holds:
                rows.append((f"CMO_{cmo:.2f}_H{hold}", TradePolicy(
                    cmo_floor=cmo, slope_bars=base.slope_bars,
                    stop_atr=base.stop_atr, trail_atr=base.trail_atr,
                    max_hold_bars=hold,
                )))

    elif round_no == 4:
        for slope in (0, 24, 72):
            for hold in _nearby_holds(base.max_hold_bars):
                rows.append((f"S{slope}_H{hold}", TradePolicy(
                    cmo_floor=base.cmo_floor, slope_bars=slope,
                    stop_atr=base.stop_atr, trail_atr=base.trail_atr,
                    max_hold_bars=hold,
                )))

    elif round_no == 5:
        holds = _nearby_holds(base.max_hold_bars)
        for hold in holds:
            for stop in (0.75, 1.0, 1.25, 1.5):
                for trail in (0.75, 1.0, 1.25, 1.5):
                    rows.append((f"H{hold}_S{stop}_T{trail}", TradePolicy(
                        cmo_floor=base.cmo_floor, slope_bars=base.slope_bars,
                        stop_atr=stop, trail_atr=trail, max_hold_bars=hold,
                    )))

    elif round_no == 6:
        cmos = sorted({
            _clamp(base.cmo_floor + delta, 0.0, 0.65)
            for delta in (-0.05, 0.0, 0.05)
        })
        holds = _nearby_holds(base.max_hold_bars)
        if base.max_hold_bars <= 0:
            holds = (12, 24, 36, 48, 72)
        stop_vals = sorted({0.0, base.stop_atr, 1.0, 1.5})
        trail_vals = sorted({0.0, base.trail_atr, 1.0, 1.5})
        for cmo in cmos:
            for hold in holds:
                for stop, trail in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.5, 0.0), (0.0, 1.5)):
                    rows.append((f"FINAL_C{cmo:.2f}_H{hold}_S{stop}_T{trail}", TradePolicy(
                        cmo_floor=cmo, slope_bars=base.slope_bars,
                        stop_atr=stop if stop in stop_vals else base.stop_atr,
                        trail_atr=trail if trail in trail_vals else base.trail_atr,
                        max_hold_bars=hold,
                    )))
    else:
        raise RuntimeError(f"unsupported autonomous holding round: {round_no}")

    return _dedupe(rows)


def main() -> None:
    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    round_no = int(control["round"])
    max_rounds = int(control["max_rounds"])
    if not (1 <= round_no <= max_rounds):
        raise RuntimeError(f"invalid autonomous round {round_no}/{max_rounds}")

    start, end = _canonical_window()
    train_a_end = start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    validation_start = train_b_end

    source_rows = json.loads(SOURCES.read_text(encoding="utf-8"))["per_symbol"]
    seed_doc = json.loads(SEEDS.read_text(encoding="utf-8"))
    seed_rows = seed_doc["per_symbol"]
    if tuple(seed_rows) != SATELLITES:
        raise RuntimeError(f"seed order drifted: {tuple(seed_rows)!r}")

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol: dict[str, object] = {}
    mature: list[str] = []
    profitability_pass: list[str] = []

    for symbol in SATELLITES:
        row = seed_rows[symbol]
        params = StrategyParameters(**row["parameters"])
        base_policy = TradePolicy(**row["base_policy"])
        variants = _variants(base_policy, round_no)
        rules = _rules(client, symbol)
        proxy_symbol = str(source_rows[symbol]["history_source_for_training"])
        warmup = params.warmup_bars

        proxy = _adapt(
            client.fetch_klines(proxy_symbol, start=start - warmup * BAR, end_exclusive=end),
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
        for name, policy in variants:
            version = f"HIXTON-V5-SAT-HOLD-R{round_no}-{symbol}-{name}"
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
            both_positive = _positive(ta) and _positive(tb)
            candidate = {
                "name": name,
                "policy": asdict(policy),
                "train_a_stress": _metrics(ta),
                "train_b_stress": _metrics(tb),
                "training_both_positive": both_positive,
                "score": [str(x) for x in _score(ta, tb, policy)],
            }
            training_rows.append(candidate)
            if both_positive:
                ranked.append((_score(ta, tb, policy), name, policy, candidate))

        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            per_symbol[symbol] = {
                "round": round_no,
                "seed_parameters": asdict(params),
                "seed_policy": asdict(base_policy),
                "training_candidate_count": len(training_rows),
                "training_candidates": training_rows,
                "training_winner": None,
                "validation": None,
                "profitability_pass": False,
                "maturity_pass": False,
                "next_reason": "NO_TWO_YEAR_STRESS_POSITIVE_TRAINING_WINNER_KEEP_INCUMBENT",
            }
            continue

        _, winner_name, winner_policy, winner_training = ranked[0]
        version = f"HIXTON-V5-SAT-HOLD-FROZEN-R{round_no}-{symbol}-{winner_name}"
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
            "round": round_no,
            "seed_parameters": asdict(params),
            "seed_policy": asdict(base_policy),
            "training_candidate_count": len(training_rows),
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
            "maturity_gap": None if mature_ok else {
                "full_3y_stress_completed_trades": f_stress.metrics.completed_trades,
                "target_completed_trades": MIN_MATURE_CYCLES,
                "positive_all_windows": profit_ok,
            },
            "next_reason": (
                "MATURE"
                if mature_ok else
                "PROFITABLE_BUT_NOT_FREQUENT_ENOUGH_CONTINUE"
                if profit_ok else
                "VALIDATION_OR_STRESS_REJECTION_CONTINUE"
            ),
        }

    result = {
        "schema_version": 1,
        "study": "SATELLITE_ISOLATED_5X250_HOLDING_REFINEMENT",
        "round": round_no,
        "max_rounds": max_rounds,
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": seed_doc["protected_product_sha"],
        "capital_per_market_usdc": "250",
        "all_five_remain_active": True,
        "per_symbol": per_symbol,
        "profitability_pass_symbols": profitability_pass,
        "mature_symbols": mature,
        "mature_count": len(mature),
        "target_count": 5,
        "selection_contract": {
            "training_only_selects_policy": True,
            "two_independent_training_years_stress_positive_required": True,
            "direct_usdc_validation_rejection_only": True,
            "validation_does_not_choose_next_round": True,
            "positive_but_weak_is_not_final": True,
            "minimum_full_3y_completed_trades_target": MIN_MATURE_CYCLES,
        },
        "next_stage": (
            "SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY"
            if len(mature) == 5
            else "SATELLITE_ISOLATED_5X250_HOLDING_REFINEMENT"
            if round_no < max_rounds
            else "SATELLITE_ISOLATED_5X250_NEEDS_NEW_CAUSAL_FAMILY"
        ),
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
        "round": round_no,
        "profitability_pass_symbols": profitability_pass,
        "mature_symbols": mature,
        "mature_count": len(mature),
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()

"""Autonomous isolated 5x250 Satellite refinement using the research-only filler router.

The protected product files remain byte-identical. Maximum holding time is modeled
only through RouterConfig in research. Each bounded round selects on two independent
TRAINING years under STRESS; Direct-USDC validation is rejection-only.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.data.binance import BinancePublicClient
from hixton.domain.models import StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V1_STRATEGY
from scripts.satellite_filler_router_research import RouterConfig, run_filler_router_portfolio
from scripts.satellite_v1_evolution_research import SATELLITES, _adapt, _rules

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
    baseline = mission["canonical_core_baseline"]
    return (
        datetime.fromisoformat(str(baseline["report_start_utc"])).astimezone(timezone.utc),
        datetime.fromisoformat(str(baseline["report_end_utc"])).astimezone(timezone.utc),
    )


def _run(*, symbol, candles, rules, start, end, costs, params, policy, horizon):
    result, events = run_filler_router_portfolio(
        candles_by_symbol={symbol: candles},
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=CAPITAL,
        target_notional=CAPITAL,
        slot_count=1,
        costs=costs,
        execution_rules={symbol: rules},
        strategy_parameters_by_symbol={symbol: params},
        trade_policies_by_symbol={symbol: policy},
        symbols=(symbol,),
        core_symbols=(),
        satellite_symbols=(symbol,),
        router_config=RouterConfig(
            filler_horizon_hours=max(1, int(horizon or 24)),
            hysteresis_atr=D("0"),
            satellite_budget_fraction_of_c=D("1"),
        ),
        strategy_semantics_by_symbol={symbol: V1_STRATEGY.semantics},
        strict_core_idle_mask=False,
        soft_filler_exit_enabled=bool(horizon),
    )
    return result, events


def _payload(result) -> dict[str, object]:
    trades = list(result.trades)
    holds = [float(t.holding_hours) for t in trades]
    position_hours = sum((t.holding_hours for t in trades), D("0"))
    active_hours = sum(1 for p in result.equity_curve if p.active_position)
    calendar_hours = len(result.equity_curve)
    completed = result.metrics.completed_trades
    return {
        "ending_equity": str(result.metrics.ending_equity),
        "net_pnl": str(result.metrics.net_pnl),
        "return_pct": str(result.metrics.return_pct),
        "completed_trades": completed,
        "winning_trades": result.metrics.winning_trades,
        "losing_trades": result.metrics.losing_trades,
        "win_rate_pct": None if result.metrics.win_rate_pct is None else str(result.metrics.win_rate_pct),
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "median_holding_hours": None if not holds else str(statistics.median(holds)),
        "average_holding_hours": None if result.metrics.average_holding_hours is None else str(result.metrics.average_holding_hours),
        "max_holding_hours": None if not holds else str(max(holds)),
        "position_hours": str(position_hours),
        "active_calendar_pct": "0" if not calendar_hours else str(D(active_hours) / D(calendar_hours) * D("100")),
        "profit_per_position_hour": None if position_hours <= 0 else str(result.metrics.net_pnl / position_hours),
        "cycles_per_1000_position_hours": None if position_hours <= 0 else str(D(completed) / position_hours * D("1000")),
        "entry_signal_count": sum(1 for s in result.signals if s.action.value == "ENTER_LONG"),
        "exit_signal_count": sum(1 for s in result.signals if s.action.value == "EXIT_LONG"),
        "blocked_signal_count": len(result.blocked_signals),
        "open_position_at_end": bool(result.open_symbols_at_end),
    }


def _positive(result) -> bool:
    return result.metrics.net_pnl > 0 and result.metrics.completed_trades > 0


def _position_hours(result) -> D:
    return sum((t.holding_hours for t in result.trades), D("0"))


def _score(a, b, horizon: int) -> tuple[D, D, int, D, int]:
    pa, pb = D(str(a.metrics.net_pnl)), D(str(b.metrics.net_pnl))
    ha, hb = _position_hours(a), _position_hours(b)
    ppha = pa / ha if ha > 0 else D("-999")
    pphb = pb / hb if hb > 0 else D("-999")
    return (
        min(pa, pb),
        min(ppha, pphb),
        min(a.metrics.completed_trades, b.metrics.completed_trades),
        pa + pb,
        -(horizon or 100000),
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    return round(max(lo, min(hi, value)), 4)


def _nearby_holds(base: int) -> tuple[int, ...]:
    if base <= 0:
        return (24, 48, 72, 120)
    vals = {max(6, base // 2), max(6, base - 24), base, min(168, base + 24), min(168, max(base + 48, base * 2))}
    return tuple(sorted(v for v in vals if 0 < v <= 168))


def _dedupe(rows: list[tuple[str, TradePolicy, int]]) -> list[tuple[str, TradePolicy, int]]:
    seen, out = set(), []
    for name, policy, horizon in rows:
        key = (policy.cmo_floor, policy.slope_bars, policy.stop_atr, policy.trail_atr, horizon)
        if key not in seen:
            seen.add(key)
            out.append((name, policy, horizon))
    return out


def _variants(base: TradePolicy, base_horizon: int, round_no: int) -> list[tuple[str, TradePolicy, int]]:
    rows: list[tuple[str, TradePolicy, int]] = [("INCUMBENT", base, base_horizon)]

    if round_no == 1:
        for hold in (24, 48, 72, 120, 168):
            rows.append((f"HOLD_{hold}", base, hold))
        for hold in (48, 72, 120):
            for atr in (1.0, 1.5, 2.0):
                rows.append((f"H{hold}_STOP_{atr}", TradePolicy(base.cmo_floor, base.slope_bars, atr, 0.0), hold))
                rows.append((f"H{hold}_TRAIL_{atr}", TradePolicy(base.cmo_floor, base.slope_bars, 0.0, atr), hold))
    elif round_no == 2:
        for hold in (6, 12, 18, 24, 36, 48):
            rows.append((f"SHORT_HOLD_{hold}", base, hold))
            for atr in (0.75, 1.0, 1.25):
                rows.append((f"H{hold}_STOP_{atr}", TradePolicy(base.cmo_floor, base.slope_bars, atr, 0.0), hold))
                rows.append((f"H{hold}_TRAIL_{atr}", TradePolicy(base.cmo_floor, base.slope_bars, 0.0, atr), hold))
    elif round_no == 3:
        for cmo in sorted({_clamp(base.cmo_floor + d, 0.0, 0.65) for d in (-0.10, -0.05, 0.0, 0.05, 0.10)}):
            for hold in _nearby_holds(base_horizon):
                rows.append((f"CMO_{cmo:.2f}_H{hold}", TradePolicy(cmo, base.slope_bars, base.stop_atr, base.trail_atr), hold))
    elif round_no == 4:
        for slope in (0, 24, 72):
            for hold in _nearby_holds(base_horizon):
                rows.append((f"S{slope}_H{hold}", TradePolicy(base.cmo_floor, slope, base.stop_atr, base.trail_atr), hold))
    elif round_no == 5:
        for hold in _nearby_holds(base_horizon):
            for stop in (0.75, 1.0, 1.25, 1.5):
                for trail in (0.75, 1.0, 1.25, 1.5):
                    rows.append((f"H{hold}_S{stop}_T{trail}", TradePolicy(base.cmo_floor, base.slope_bars, stop, trail), hold))
    elif round_no == 6:
        holds = _nearby_holds(base_horizon) if base_horizon else (12, 24, 36, 48, 72)
        for cmo in sorted({_clamp(base.cmo_floor + d, 0.0, 0.65) for d in (-0.05, 0.0, 0.05)}):
            for hold in holds:
                for stop, trail in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.5, 0.0), (0.0, 1.5)):
                    rows.append((f"FINAL_C{cmo:.2f}_H{hold}_S{stop}_T{trail}", TradePolicy(cmo, base.slope_bars, stop, trail), hold))
    else:
        raise RuntimeError(f"unsupported autonomous holding round {round_no}")
    return _dedupe(rows)


def main() -> None:
    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    round_no, max_rounds = int(control["round"]), int(control["max_rounds"])
    if not (1 <= round_no <= max_rounds):
        raise RuntimeError(f"invalid round {round_no}/{max_rounds}")

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
    per_symbol, mature, profitability_pass = {}, [], []

    for symbol in SATELLITES:
        row = seed_rows[symbol]
        params = StrategyParameters(**row["parameters"])
        base_policy = TradePolicy(**row["base_policy"])
        base_horizon = int(row.get("base_horizon_hours", 0))
        variants = _variants(base_policy, base_horizon, round_no)
        rules = _rules(client, symbol)
        proxy_symbol = str(source_rows[symbol]["history_source_for_training"])
        warmup = params.warmup_bars

        proxy = _adapt(client.fetch_klines(proxy_symbol, start=start - warmup * BAR, end_exclusive=end), symbol)
        direct = client.fetch_klines(symbol, start=validation_start - warmup * BAR, end_exclusive=end)

        training_rows, ranked = [], []
        for name, policy, horizon in variants:
            ta, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=start, end=train_a_end, costs=STRESS_COSTS, params=params, policy=policy, horizon=horizon)
            tb, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=train_a_end, end=train_b_end, costs=STRESS_COSTS, params=params, policy=policy, horizon=horizon)
            both_positive = _positive(ta) and _positive(tb)
            candidate = {
                "name": name, "policy": asdict(policy), "max_holding_hours": horizon,
                "train_a_stress": _payload(ta), "train_b_stress": _payload(tb),
                "training_both_positive": both_positive,
                "score": [str(x) for x in _score(ta, tb, horizon)],
            }
            training_rows.append(candidate)
            if both_positive:
                ranked.append((_score(ta, tb, horizon), name, policy, horizon, candidate))

        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            per_symbol[symbol] = {
                "round": round_no, "seed_parameters": asdict(params), "seed_policy": asdict(base_policy),
                "seed_horizon_hours": base_horizon, "training_candidate_count": len(training_rows),
                "training_candidates": training_rows, "training_winner": None, "validation": None,
                "profitability_pass": False, "maturity_pass": False,
                "next_reason": "NO_TWO_YEAR_STRESS_POSITIVE_TRAINING_WINNER_KEEP_INCUMBENT",
            }
            continue

        _, winner_name, winner_policy, winner_horizon, winner_training = ranked[0]
        v_base, _ = _run(symbol=symbol, candles=direct, rules=rules, start=validation_start, end=end, costs=BASELINE_COSTS, params=params, policy=winner_policy, horizon=winner_horizon)
        v_stress, _ = _run(symbol=symbol, candles=direct, rules=rules, start=validation_start, end=end, costs=STRESS_COSTS, params=params, policy=winner_policy, horizon=winner_horizon)
        f_base, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=start, end=end, costs=BASELINE_COSTS, params=params, policy=winner_policy, horizon=winner_horizon)
        f_stress, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=start, end=end, costs=STRESS_COSTS, params=params, policy=winner_policy, horizon=winner_horizon)

        profit_ok = all(_positive(x) for x in (v_base, v_stress, f_base, f_stress))
        mature_ok = profit_ok and f_stress.metrics.completed_trades >= MIN_MATURE_CYCLES
        if profit_ok: profitability_pass.append(symbol)
        if mature_ok: mature.append(symbol)

        per_symbol[symbol] = {
            "round": round_no, "seed_parameters": asdict(params), "seed_policy": asdict(base_policy),
            "seed_horizon_hours": base_horizon, "training_candidate_count": len(training_rows),
            "training_candidates": training_rows,
            "training_winner": {"name": winner_name, "policy": asdict(winner_policy), "max_holding_hours": winner_horizon, "training": winner_training},
            "validation": {"baseline": _payload(v_base), "stress": _payload(v_stress), "full_3y_proxy_baseline": _payload(f_base), "full_3y_proxy_stress": _payload(f_stress)},
            "profitability_pass": profit_ok, "maturity_pass": mature_ok,
            "maturity_gap": None if mature_ok else {"full_3y_stress_completed_trades": f_stress.metrics.completed_trades, "target_completed_trades": MIN_MATURE_CYCLES, "positive_all_windows": profit_ok},
            "next_reason": "MATURE" if mature_ok else "PROFITABLE_BUT_NOT_FREQUENT_ENOUGH_CONTINUE" if profit_ok else "VALIDATION_OR_STRESS_REJECTION_CONTINUE",
        }

    result = {
        "schema_version": 2, "study": "SATELLITE_ISOLATED_5X250_HOLDING_REFINEMENT",
        "round": round_no, "max_rounds": max_rounds, "research_only": True, "product_mutated": False,
        "protected_product_sha": seed_doc["protected_product_sha"], "capital_per_market_usdc": "250",
        "all_five_remain_active": True, "per_symbol": per_symbol,
        "profitability_pass_symbols": profitability_pass, "mature_symbols": mature, "mature_count": len(mature), "target_count": 5,
        "selection_contract": {"training_only_selects_policy_and_horizon": True, "two_independent_training_years_stress_positive_required": True, "direct_usdc_validation_rejection_only": True, "validation_does_not_choose_next_round": True, "positive_but_weak_is_not_final": True, "minimum_full_3y_completed_trades_target": MIN_MATURE_CYCLES},
        "next_stage": "SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY" if len(mature) == 5 else "SATELLITE_ISOLATED_5X250_HOLDING_REFINEMENT" if round_no < max_rounds else "SATELLITE_ISOLATED_5X250_NEEDS_NEW_CAUSAL_FAMILY",
        "safety": {"protected_core_mutated": False, "product_critical_files_modified_for_horizon": False, "orders_sent": False, "paper_or_live_activated": False, "private_credentials_used": False},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"study": result["study"], "round": round_no, "profitability_pass_symbols": profitability_pass, "mature_symbols": mature, "mature_count": len(mature), "next_stage": result["next_stage"]}, indent=2))


if __name__ == "__main__":
    main()

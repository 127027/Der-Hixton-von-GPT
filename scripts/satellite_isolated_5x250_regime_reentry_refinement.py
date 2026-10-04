"""Regime-aware and pullback-reentry isolated Satellite research.

This is the first materially different family after the exhausted holding/CMO/slope/
stop-trail rounds. It keeps product/Core code untouched, selects only from two
independent TRAINING years under STRESS, and uses Direct-USDC/full-window evidence
only to reject or classify the training winner.

Key new ideas:
- point-in-time volatility regime using ATR/close;
- point-in-time trend extension using (close-VIDYA)/ATR;
- breakout-quality floor for canonical flip-up entries;
- research-only continuation re-entry after a completed pullback through VIDYA while
  the canonical trend remains UP.

The mature NEAR incumbent is frozen and not allowed to regress.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.data.binance import BinancePublicClient
from hixton.domain.models import IndicatorPoint, StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V1_STRATEGY
from scripts.satellite_filler_router_research import RouterConfig, run_filler_router_portfolio
from scripts.satellite_isolated_5x250_holding_refinement import (
    BAR,
    CAPITAL,
    MIN_MATURE_CYCLES,
    _canonical_window,
    _payload,
    _positive,
    _position_hours,
)
from scripts.satellite_v1_evolution_research import SATELLITES, _adapt, _rules

D = Decimal
MISSION = Path("agent_memory/autonomy/current_mission.json")
SOURCES = Path("agent_memory/autonomy/satellite_v1_idle_horizon_sources.json")
INCUMBENTS = Path("agent_memory/autonomy/satellite_validated_incumbents.json")
OUTPUT = Path("evidence/satellite-isolated-5x250-regime-reentry-refinement.json")


@dataclass(frozen=True, slots=True)
class RegimeSpec:
    name: str
    reentry: bool = False
    horizon_hours: int = 0
    min_atr_pct: float = 0.0
    max_atr_pct: float = 1.0
    min_trend_atr: float = -999.0
    max_trend_atr: float = 999.0
    min_breakout_atr: float = 0.0
    min_abs_cmo: float = 0.0


def _specs(base_horizon: int) -> tuple[RegimeSpec, ...]:
    incumbent_h = max(0, int(base_horizon))
    return (
        RegimeSpec("INCUMBENT", horizon_hours=incumbent_h),
        RegimeSpec("VOL_MAX_2PCT", horizon_hours=incumbent_h, max_atr_pct=0.020),
        RegimeSpec("VOL_0P3_TO_3P0", horizon_hours=incumbent_h, min_atr_pct=0.003, max_atr_pct=0.030),
        RegimeSpec("TREND_0P25_TO_3", horizon_hours=incumbent_h, min_trend_atr=0.25, max_trend_atr=3.0),
        RegimeSpec("TREND_0P50_TO_2P5", horizon_hours=incumbent_h, min_trend_atr=0.50, max_trend_atr=2.5),
        RegimeSpec("BREAKOUT_0P10", horizon_hours=incumbent_h, min_breakout_atr=0.10),
        RegimeSpec("BREAKOUT_0P25", horizon_hours=incumbent_h, min_breakout_atr=0.25),
        RegimeSpec(
            "REGIME_BALANCED",
            horizon_hours=incumbent_h,
            min_atr_pct=0.003,
            max_atr_pct=0.025,
            min_trend_atr=0.25,
            max_trend_atr=2.5,
        ),
        RegimeSpec(
            "REENTRY_H24_LIGHT",
            reentry=True,
            horizon_hours=24,
            min_atr_pct=0.002,
            max_atr_pct=0.040,
            min_trend_atr=0.0,
            max_trend_atr=2.0,
            min_abs_cmo=0.05,
        ),
        RegimeSpec(
            "REENTRY_H48_LIGHT",
            reentry=True,
            horizon_hours=48,
            min_atr_pct=0.002,
            max_atr_pct=0.040,
            min_trend_atr=0.0,
            max_trend_atr=2.0,
            min_abs_cmo=0.05,
        ),
        RegimeSpec(
            "REENTRY_H48_BALANCED",
            reentry=True,
            horizon_hours=48,
            min_atr_pct=0.003,
            max_atr_pct=0.030,
            min_trend_atr=0.0,
            max_trend_atr=1.5,
            min_abs_cmo=0.10,
        ),
        RegimeSpec(
            "REENTRY_H72_BALANCED",
            reentry=True,
            horizon_hours=72,
            min_atr_pct=0.003,
            max_atr_pct=0.030,
            min_trend_atr=0.0,
            max_trend_atr=1.5,
            min_abs_cmo=0.10,
        ),
    )


def _entry_filter(spec: RegimeSpec):
    def gate(point: IndicatorPoint) -> str | None:
        if point.atr is None or point.vidya is None or point.candle.close <= 0 or point.atr <= 0:
            return "REGIME_INPUT_UNAVAILABLE"
        atr_pct = point.atr / point.candle.close
        trend_atr = (point.candle.close - point.vidya) / point.atr
        breakout = point.breakout_strength or 0.0
        abs_cmo = point.abs_cmo or 0.0
        if atr_pct < spec.min_atr_pct:
            return "REGIME_ATR_TOO_LOW"
        if atr_pct > spec.max_atr_pct:
            return "REGIME_ATR_TOO_HIGH"
        if trend_atr < spec.min_trend_atr:
            return "REGIME_TREND_TOO_WEAK"
        if trend_atr > spec.max_trend_atr:
            return "REGIME_TREND_TOO_EXTENDED"
        if breakout < spec.min_breakout_atr:
            return "REGIME_BREAKOUT_TOO_WEAK"
        if abs_cmo < spec.min_abs_cmo:
            return "REGIME_CMO_TOO_WEAK"
        return None

    return gate


def _run(*, symbol, candles, rules, start, end, costs, params, policy, spec):
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
            filler_horizon_hours=max(1, int(spec.horizon_hours or 24)),
            hysteresis_atr=D("0"),
            satellite_budget_fraction_of_c=D("1"),
        ),
        strategy_semantics_by_symbol={symbol: V1_STRATEGY.semantics},
        strict_core_idle_mask=False,
        soft_filler_exit_enabled=bool(spec.horizon_hours),
        entry_filter_by_symbol={symbol: _entry_filter(spec)},
        continuation_reentry_symbols=frozenset({symbol}) if spec.reentry else frozenset(),
    )
    return result, events


def _score(a, b) -> tuple[D, D, int, D, D]:
    pa, pb = D(str(a.metrics.net_pnl)), D(str(b.metrics.net_pnl))
    ha, hb = _position_hours(a), _position_hours(b)
    ppha = pa / ha if ha > 0 else D("-999")
    pphb = pb / hb if hb > 0 else D("-999")
    return (
        min(pa, pb),
        min(ppha, pphb),
        min(a.metrics.completed_trades, b.metrics.completed_trades),
        pa + pb,
        -max(D(str(a.metrics.max_drawdown_pct)), D(str(b.metrics.max_drawdown_pct))),
    )


def _reference_delta(reference: dict, v_stress, f_stress, profit_ok: bool, mature_ok: bool) -> dict:
    ref = reference["reference"]
    ref_val = D(str(ref["validation_stress_net_pnl"]))
    ref_full = D(str(ref["full_3y_stress_net_pnl"]))
    ref_trades = int(ref["full_3y_stress_trades"])
    ref_dd = D(str(ref["full_3y_stress_max_drawdown_pct"]))
    ref_pph = D(str(ref["full_3y_stress_profit_per_position_hour"]))

    cand_val = D(str(v_stress.metrics.net_pnl))
    cand_full = D(str(f_stress.metrics.net_pnl))
    cand_trades = int(f_stress.metrics.completed_trades)
    cand_dd = D(str(f_stress.metrics.max_drawdown_pct))
    hours = _position_hours(f_stress)
    cand_pph = cand_full / hours if hours > 0 else D("-999")

    ref_profit = bool(reference["profitability_pass"])
    ref_mature = bool(reference["maturity_pass"])

    no_pnl_regression = cand_full >= ref_full and cand_val >= ref_val
    no_risk_regression = cand_dd <= ref_dd
    activity_non_regressive = cand_trades >= ref_trades
    pph_non_regressive = cand_pph >= ref_pph

    improved = False
    reason = "NO_DOMINANT_IMPROVEMENT"
    if profit_ok and not ref_profit and no_pnl_regression:
        improved = True
        reason = "BECAME_ROBUSTLY_PROFITABLE"
    elif profit_ok and ref_profit:
        if mature_ok and not ref_mature and no_pnl_regression:
            improved = True
            reason = "BECAME_MATURE_WITHOUT_PNL_REGRESSION"
        elif no_pnl_regression and (activity_non_regressive or pph_non_regressive) and (
            cand_full > ref_full or cand_val > ref_val or cand_trades > ref_trades or cand_pph > ref_pph
        ):
            improved = True
            reason = "STRICT_ROBUST_DOMINANCE"
    elif not ref_profit and not profit_ok:
        if no_pnl_regression and no_risk_regression and (
            cand_val > ref_val or cand_full > ref_full or cand_trades > ref_trades or cand_pph > ref_pph
        ):
            improved = True
            reason = "RESEARCH_REFERENCE_IMPROVED_BUT_NOT_YET_ROBUST"

    classification = "IMPROVED" if improved else "UNCHANGED"
    if cand_full < ref_full and cand_val < ref_val and cand_dd > ref_dd:
        classification = "WORSE"
        reason = "PNL_AND_RISK_REGRESSION"

    return {
        "classification": classification,
        "reason": reason,
        "validation_stress_net_pnl_delta": str(cand_val - ref_val),
        "full_3y_stress_net_pnl_delta": str(cand_full - ref_full),
        "full_3y_stress_completed_trades_delta": cand_trades - ref_trades,
        "full_3y_stress_max_drawdown_pct_delta": str(cand_dd - ref_dd),
        "full_3y_stress_profit_per_position_hour_delta": str(cand_pph - ref_pph),
        "candidate_profitability_pass": profit_ok,
        "candidate_maturity_pass": mature_ok,
        "reference_profitability_pass": ref_profit,
        "reference_maturity_pass": ref_mature,
    }


def main() -> None:
    start, end = _canonical_window()
    train_a_end = start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    validation_start = train_b_end

    source_rows = json.loads(SOURCES.read_text(encoding="utf-8"))["per_symbol"]
    incumbents = json.loads(INCUMBENTS.read_text(encoding="utf-8"))
    inc_rows = incumbents["per_symbol"]

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol = {}
    improved_symbols = []
    profitability_pass_symbols = []
    mature_symbols = []

    for symbol in SATELLITES:
        incumbent = inc_rows[symbol]
        params = StrategyParameters(**incumbent["parameters"])
        policy = TradePolicy(**incumbent["policy"])
        rules = _rules(client, symbol)

        if incumbent["maturity_pass"]:
            per_symbol[symbol] = {
                "status": "FROZEN_MATURE_INCUMBENT",
                "source_run": incumbent["source_run"],
                "reference": incumbent["reference"],
                "classification": "UNCHANGED",
                "reason": "MATURE_INCUMBENT_PROTECTED_FROM_REGRESSION",
            }
            profitability_pass_symbols.append(symbol)
            mature_symbols.append(symbol)
            continue

        proxy_symbol = str(source_rows[symbol]["history_source_for_training"])
        warmup = params.warmup_bars
        proxy = _adapt(client.fetch_klines(proxy_symbol, start=start - warmup * BAR, end_exclusive=end), symbol)
        direct = client.fetch_klines(symbol, start=validation_start - warmup * BAR, end_exclusive=end)

        training_rows = []
        ranked = []
        for spec in _specs(int(incumbent["horizon_hours"])):
            ta, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=start, end=train_a_end, costs=STRESS_COSTS, params=params, policy=policy, spec=spec)
            tb, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=train_a_end, end=train_b_end, costs=STRESS_COSTS, params=params, policy=policy, spec=spec)
            both_positive = _positive(ta) and _positive(tb)
            row = {
                "spec": asdict(spec),
                "train_a_stress": _payload(ta),
                "train_b_stress": _payload(tb),
                "training_both_positive": both_positive,
                "score": [str(x) for x in _score(ta, tb)],
            }
            training_rows.append(row)
            if both_positive:
                ranked.append((_score(ta, tb), spec, row))

        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            per_symbol[symbol] = {
                "status": "NO_TWO_YEAR_STRESS_POSITIVE_TRAINING_WINNER",
                "training_candidates": training_rows,
                "classification": "UNCHANGED",
                "reason": "NEW_FAMILY_FAILED_TRAINING_ROBUSTNESS",
                "reference": incumbent["reference"],
            }
            continue

        _, winner_spec, winner_training = ranked[0]
        v_base, _ = _run(symbol=symbol, candles=direct, rules=rules, start=validation_start, end=end, costs=BASELINE_COSTS, params=params, policy=policy, spec=winner_spec)
        v_stress, _ = _run(symbol=symbol, candles=direct, rules=rules, start=validation_start, end=end, costs=STRESS_COSTS, params=params, policy=policy, spec=winner_spec)
        f_base, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=start, end=end, costs=BASELINE_COSTS, params=params, policy=policy, spec=winner_spec)
        f_stress, _ = _run(symbol=symbol, candles=proxy, rules=rules, start=start, end=end, costs=STRESS_COSTS, params=params, policy=policy, spec=winner_spec)

        profit_ok = all(_positive(x) for x in (v_base, v_stress, f_base, f_stress))
        mature_ok = profit_ok and f_stress.metrics.completed_trades >= MIN_MATURE_CYCLES
        if profit_ok:
            profitability_pass_symbols.append(symbol)
        if mature_ok:
            mature_symbols.append(symbol)

        delta = _reference_delta(incumbent, v_stress, f_stress, profit_ok, mature_ok)
        if delta["classification"] == "IMPROVED":
            improved_symbols.append(symbol)

        per_symbol[symbol] = {
            "status": "TRAINING_WINNER_VALIDATED",
            "training_candidate_count": len(training_rows),
            "training_candidates": training_rows,
            "training_winner": {"spec": asdict(winner_spec), "training": winner_training},
            "validation": {
                "baseline": _payload(v_base),
                "stress": _payload(v_stress),
                "full_3y_proxy_baseline": _payload(f_base),
                "full_3y_proxy_stress": _payload(f_stress),
            },
            "profitability_pass": profit_ok,
            "maturity_pass": mature_ok,
            "reference_source_run": incumbent["source_run"],
            "reference": incumbent["reference"],
            "economic_delta_vs_reference": delta,
            "classification": delta["classification"],
            "reason": delta["reason"],
        }

    result = {
        "schema_version": 1,
        "study": "SATELLITE_ISOLATED_5X250_REGIME_REENTRY_REFINEMENT",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": incumbents["protected_product_sha"],
        "capital_per_market_usdc": "250",
        "family": "POINT_IN_TIME_REGIME_PLUS_PULLBACK_REENTRY",
        "selection_contract": {
            "two_independent_training_years_stress_positive_required": True,
            "training_only_selects_candidate": True,
            "direct_usdc_validation_rejection_only": True,
            "validated_incumbent_never_overwritten_by_worse_candidate": True,
            "no_future_information": True,
        },
        "per_symbol": per_symbol,
        "improved_symbols": improved_symbols,
        "profitability_pass_symbols": profitability_pass_symbols,
        "mature_symbols": mature_symbols,
        "economic_progress": bool(improved_symbols),
        "next_stage": (
            "SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY"
            if len(mature_symbols) == 5
            else "SATELLITE_ISOLATED_5X250_NEEDS_NEXT_PATCH"
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
        "improved_symbols": improved_symbols,
        "profitability_pass_symbols": profitability_pass_symbols,
        "mature_symbols": mature_symbols,
        "economic_progress": result["economic_progress"],
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()

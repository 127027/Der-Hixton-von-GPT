"""Targeted post-Run-114 Satellite refinement.

Run #114 produced real economic progress but different weaknesses per market.
This stage uses those training findings causally instead of repeating the same grid:
- SUI/BCH: locally refine the successful low-volatility cap.
- AAVE: locally refine the successful balanced regime window.
- UNI: preserve its validated incumbent and test a stricter upper-band continuation
  re-entry family to seek additional opportunities without the noisy VIDYA re-entry.
- NEAR: frozen mature incumbent.

Selection remains TRAINING-only on two independent stress years. Direct-USDC and
full-window evidence are rejection/classification only.
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
from scripts.satellite_isolated_5x250_regime_reentry_refinement import (
    RegimeSpec,
    _entry_filter,
)
from scripts.satellite_v1_evolution_research import SATELLITES, _adapt, _rules

D = Decimal
SOURCES = Path("agent_memory/autonomy/satellite_v1_idle_horizon_sources.json")
PARAMS = Path("agent_memory/autonomy/satellite_validated_incumbents.json")
STATE = Path("agent_memory/autonomy/satellite_post114_state.json")
OUTPUT = Path("evidence/satellite-isolated-5x250-post114-targeted-refinement.json")


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    regime: RegimeSpec
    band_reentry: bool = False


def _candidates(symbol: str, base: dict) -> tuple[Candidate, ...]:
    b = RegimeSpec(**base)
    rows: list[Candidate] = [Candidate("REFERENCE_FAMILY", b, False)]

    if symbol in {"SUIUSDC", "BCHUSDC"}:
        for cap in (0.015, 0.0175, 0.020, 0.0225, 0.025, 0.030):
            rows.append(Candidate(
                f"VOL_CAP_{cap:.4f}",
                RegimeSpec(
                    name=f"VOL_CAP_{cap:.4f}",
                    horizon_hours=0,
                    min_atr_pct=0.0,
                    max_atr_pct=cap,
                ),
            ))
        for floor, cap in ((0.0015,0.020),(0.0020,0.020),(0.0025,0.0225)):
            rows.append(Candidate(
                f"VOL_BAND_{floor:.4f}_{cap:.4f}",
                RegimeSpec(
                    name=f"VOL_BAND_{floor:.4f}_{cap:.4f}",
                    horizon_hours=0,
                    min_atr_pct=floor,
                    max_atr_pct=cap,
                ),
            ))

    elif symbol == "AAVEUSDC":
        settings = (
            (0.0020,0.025,0.15,2.5),
            (0.0025,0.025,0.20,2.5),
            (0.0030,0.025,0.25,2.5),
            (0.0035,0.025,0.30,2.5),
            (0.0030,0.020,0.25,2.5),
            (0.0030,0.030,0.25,2.5),
            (0.0030,0.025,0.15,2.0),
            (0.0030,0.025,0.25,2.0),
            (0.0030,0.025,0.40,2.0),
            (0.0030,0.025,0.25,3.0),
        )
        for lo, hi, tlo, thi in settings:
            name=f"AAVE_R_{lo:.4f}_{hi:.4f}_T{tlo:.2f}_{thi:.2f}"
            rows.append(Candidate(
                name,
                RegimeSpec(
                    name=name,
                    horizon_hours=0,
                    min_atr_pct=lo,
                    max_atr_pct=hi,
                    min_trend_atr=tlo,
                    max_trend_atr=thi,
                ),
            ))

    elif symbol == "UNIUSDC":
        # The broad VIDYA-cross re-entry failed badly in Run #114 training.
        # Test only stricter upper-band continuation entries with bounded occupancy.
        settings = (
            (48,0.0,1.0,0.00),
            (72,0.0,1.0,0.00),
            (120,0.0,1.0,0.00),
            (48,0.002,0.035,0.05),
            (72,0.002,0.035,0.05),
            (120,0.002,0.035,0.05),
            (48,0.003,0.030,0.10),
            (72,0.003,0.030,0.10),
            (120,0.003,0.030,0.10),
        )
        for hold, lo, hi, cmo in settings:
            name=f"UNI_BAND_REENTRY_H{hold}_V{lo:.3f}_{hi:.3f}_C{cmo:.2f}"
            rows.append(Candidate(
                name,
                RegimeSpec(
                    name=name,
                    horizon_hours=hold,
                    min_atr_pct=lo,
                    max_atr_pct=hi,
                    min_abs_cmo=cmo,
                ),
                True,
            ))
    return tuple(rows)


def _run(*, symbol, candles, rules, start, end, costs, params, policy, candidate: Candidate):
    spec = candidate.regime
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
        continuation_reentry_symbols=frozenset(),
        band_reentry_symbols=frozenset({symbol}) if candidate.band_reentry else frozenset(),
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


def _delta(reference_row: dict, v_stress, f_stress, profit_ok: bool, mature_ok: bool) -> dict:
    ref = reference_row["reference"]
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
    ref_profit = bool(reference_row.get("profitability_pass", False))
    ref_mature = bool(reference_row.get("maturity_pass", False))

    improved = False
    reason = "NO_DOMINANT_IMPROVEMENT"
    if profit_ok and not ref_profit and cand_val > ref_val and cand_full >= ref_full:
        improved, reason = True, "BECAME_ROBUSTLY_PROFITABLE"
    elif profit_ok and ref_profit:
        if mature_ok and not ref_mature and cand_val >= ref_val and cand_full >= ref_full:
            improved, reason = True, "BECAME_MATURE_WITHOUT_PNL_REGRESSION"
        elif cand_val >= ref_val and cand_full >= ref_full and (
            cand_val > ref_val or cand_full > ref_full or cand_trades > ref_trades or cand_pph > ref_pph or cand_dd < ref_dd
        ):
            improved, reason = True, "ROBUST_DOMINANCE"
    elif not ref_profit and not profit_ok and cand_full >= ref_full and (
        cand_val > ref_val or cand_full > ref_full or cand_dd < ref_dd or cand_pph > ref_pph
    ):
        improved, reason = True, "RESEARCH_BENCHMARK_IMPROVED"

    classification = "IMPROVED" if improved else "UNCHANGED"
    if cand_val < ref_val and cand_full < ref_full and cand_dd > ref_dd:
        classification, reason = "WORSE", "PNL_AND_RISK_REGRESSION"

    return {
        "classification": classification,
        "reason": reason,
        "validation_stress_net_pnl_delta": str(cand_val-ref_val),
        "full_3y_stress_net_pnl_delta": str(cand_full-ref_full),
        "full_3y_stress_completed_trades_delta": cand_trades-ref_trades,
        "full_3y_stress_max_drawdown_pct_delta": str(cand_dd-ref_dd),
        "full_3y_stress_profit_per_position_hour_delta": str(cand_pph-ref_pph),
        "candidate_profitability_pass": profit_ok,
        "candidate_maturity_pass": mature_ok,
    }


def main() -> None:
    start, end = _canonical_window()
    train_a_end = start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    validation_start = train_b_end

    source_rows = json.loads(SOURCES.read_text(encoding="utf-8"))["per_symbol"]
    params_rows = json.loads(PARAMS.read_text(encoding="utf-8"))["per_symbol"]
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state_rows = state["per_symbol"]

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol = {}
    improved_symbols: list[str] = []
    profitability_pass: list[str] = []
    mature: list[str] = []

    for symbol in SATELLITES:
        ref = state_rows[symbol]
        if ref["status"] == "FROZEN_MATURE_INCUMBENT":
            per_symbol[symbol] = {
                "status": "FROZEN_MATURE_INCUMBENT",
                "classification": "UNCHANGED",
                "reference": ref["reference"],
                "reason": "MATURE_INCUMBENT_PROTECTED",
            }
            profitability_pass.append(symbol)
            mature.append(symbol)
            continue

        psrc = params_rows[symbol]
        params = StrategyParameters(**psrc["parameters"])
        policy = TradePolicy(**psrc["policy"])
        rules = _rules(client, symbol)
        warmup = params.warmup_bars
        proxy_symbol = str(source_rows[symbol]["history_source_for_training"])
        proxy = _adapt(client.fetch_klines(proxy_symbol, start=start-warmup*BAR, end_exclusive=end), symbol)
        direct = client.fetch_klines(symbol, start=validation_start-warmup*BAR, end_exclusive=end)

        rows = []
        ranked = []
        for candidate in _candidates(symbol, ref["base_spec"]):
            ta,_ = _run(symbol=symbol,candles=proxy,rules=rules,start=start,end=train_a_end,costs=STRESS_COSTS,params=params,policy=policy,candidate=candidate)
            tb,_ = _run(symbol=symbol,candles=proxy,rules=rules,start=train_a_end,end=train_b_end,costs=STRESS_COSTS,params=params,policy=policy,candidate=candidate)
            both = _positive(ta) and _positive(tb)
            row={"candidate":{"name":candidate.name,"regime":asdict(candidate.regime),"band_reentry":candidate.band_reentry},"train_a_stress":_payload(ta),"train_b_stress":_payload(tb),"training_both_positive":both,"score":[str(x) for x in _score(ta,tb)]}
            rows.append(row)
            if both:
                ranked.append((_score(ta,tb),candidate,row))

        ranked.sort(key=lambda x:x[0], reverse=True)
        if not ranked:
            per_symbol[symbol]={"status":"NO_TWO_YEAR_STRESS_POSITIVE_TRAINING_WINNER","classification":"UNCHANGED","training_candidates":rows,"reference":ref["reference"],"reason":"TARGETED_FAMILY_FAILED_TRAINING"}
            continue

        _,winner,winner_training=ranked[0]
        v_base,_=_run(symbol=symbol,candles=direct,rules=rules,start=validation_start,end=end,costs=BASELINE_COSTS,params=params,policy=policy,candidate=winner)
        v_stress,_=_run(symbol=symbol,candles=direct,rules=rules,start=validation_start,end=end,costs=STRESS_COSTS,params=params,policy=policy,candidate=winner)
        f_base,_=_run(symbol=symbol,candles=proxy,rules=rules,start=start,end=end,costs=BASELINE_COSTS,params=params,policy=policy,candidate=winner)
        f_stress,_=_run(symbol=symbol,candles=proxy,rules=rules,start=start,end=end,costs=STRESS_COSTS,params=params,policy=policy,candidate=winner)

        profit_ok=all(_positive(x) for x in (v_base,v_stress,f_base,f_stress))
        mature_ok=profit_ok and f_stress.metrics.completed_trades>=MIN_MATURE_CYCLES
        if profit_ok: profitability_pass.append(symbol)
        if mature_ok: mature.append(symbol)
        delta=_delta(ref,v_stress,f_stress,profit_ok,mature_ok)
        if delta["classification"]=="IMPROVED": improved_symbols.append(symbol)

        per_symbol[symbol]={
            "status":"TRAINING_WINNER_VALIDATED",
            "training_candidates":rows,
            "training_winner":{"candidate":{"name":winner.name,"regime":asdict(winner.regime),"band_reentry":winner.band_reentry},"training":winner_training},
            "validation":{"baseline":_payload(v_base),"stress":_payload(v_stress),"full_3y_proxy_baseline":_payload(f_base),"full_3y_proxy_stress":_payload(f_stress)},
            "profitability_pass":profit_ok,"maturity_pass":mature_ok,
            "reference_source_run":ref["reference_source_run"],"reference":ref["reference"],
            "economic_delta_vs_reference":delta,"classification":delta["classification"],"reason":delta["reason"],
        }

    result={
        "schema_version":1,
        "study":"SATELLITE_ISOLATED_5X250_POST114_TARGETED_REFINEMENT",
        "research_only":True,
        "product_mutated":False,
        "source_run":114,
        "capital_per_market_usdc":"250",
        "family":"TARGETED_LOCAL_REGIME_PLUS_UPPER_BAND_REENTRY",
        "per_symbol":per_symbol,
        "improved_symbols":improved_symbols,
        "profitability_pass_symbols":profitability_pass,
        "mature_symbols":mature,
        "economic_progress":bool(improved_symbols),
        "next_stage":"SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY" if len(mature)==5 else "SATELLITE_ISOLATED_5X250_NEEDS_NEXT_PATCH",
        "selection_contract":{"training_only_selects":True,"two_independent_training_years_stress_positive_required":True,"validation_rejection_only":True,"validated_incumbent_no_regression":True},
        "safety":{"protected_core_mutated":False,"orders_sent":False,"paper_or_live_activated":False,"private_credentials_used":False},
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps({"study":result["study"],"improved_symbols":improved_symbols,"profitability_pass_symbols":profitability_pass,"mature_symbols":mature,"economic_progress":result["economic_progress"],"next_stage":result["next_stage"]},indent=2))


if __name__=="__main__":
    main()

"""Persistent autonomous isolated 5x250 Satellite improvement cycle.

Each round is a materially different point-in-time research family. The script:
- keeps NEAR frozen once mature;
- keeps TRAINING_RESEARCH_SEED separate from the validated/reference benchmark;
- chooses the next seed from two independent TRAINING years under STRESS only;
- uses Direct-USDC/full-window evidence only for rejection/reference classification;
- treats a green workflow as technical success, never as economic progress by itself.

The accompanying handoff script persists the training winner, accepts only genuine
reference improvements, advances to the next causal family and explicitly dispatches
one new workflow run.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, replace
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
CONTROL = Path("agent_memory/autonomy/satellite_adaptive_control.json")
STATE = Path("agent_memory/autonomy/satellite_adaptive_state.json")
OUTPUT = Path("evidence/satellite-isolated-5x250-adaptive-cycle.json")
TRAINING_PNL_RETENTION_FOR_ACTIVITY = D("0.75")


@dataclass(frozen=True, slots=True)
class AdaptiveSpec:
    name: str
    horizon_hours: int = 0
    min_atr_pct: float = 0.0
    max_atr_pct: float = 1.0
    min_trend_atr: float = -999.0
    max_trend_atr: float = 999.0
    min_breakout_atr: float = 0.0
    min_abs_cmo: float = 0.0
    reentry_atr_level: float | None = None
    atr_direction: str | None = None
    trend_health_exit: float | None = None
    min_rank_strength: float = -999.0
    max_rank_strength: float = 999.0


def _seed(row: dict) -> AdaptiveSpec:
    return AdaptiveSpec(**row["training_seed"])


def _with(seed: AdaptiveSpec, name: str, **changes) -> AdaptiveSpec:
    return replace(seed, name=name, **changes)


def _clamp(value: float, lo: float, hi: float) -> float:
    return round(max(lo, min(hi, value)), 5)


def _dedupe(rows: list[AdaptiveSpec]) -> tuple[AdaptiveSpec, ...]:
    out: list[AdaptiveSpec] = []
    seen = set()
    for row in rows:
        key = (
            row.horizon_hours, row.min_atr_pct, row.max_atr_pct,
            row.min_trend_atr, row.max_trend_atr, row.min_breakout_atr,
            row.min_abs_cmo, row.reentry_atr_level, row.atr_direction,
            row.trend_health_exit, row.min_rank_strength, row.max_rank_strength,
        )
        if key not in seen:
            seen.add(key)
            out.append(row)
    return tuple(out)


def _variants(symbol: str, seed: AdaptiveSpec, round_no: int) -> tuple[AdaptiveSpec, ...]:
    rows: list[AdaptiveSpec] = [_with(seed, "SEED")]

    if round_no == 1:
        if symbol in {"SUIUSDC", "UNIUSDC"}:
            for level in (0.25, 0.50, 0.75, 1.00):
                for hold in (24, 48, 72, 120):
                    rows.append(_with(
                        seed, f"ATR_REENTRY_{level:.2f}_H{hold}",
                        reentry_atr_level=level, horizon_hours=hold,
                    ))
        else:
            for threshold in (-0.50, -0.25, 0.0, 0.25):
                rows.append(_with(
                    seed, f"TREND_EXIT_{threshold:+.2f}",
                    trend_health_exit=threshold,
                ))

    elif round_no == 2:
        if symbol in {"SUIUSDC", "UNIUSDC"}:
            for threshold in (-0.50, -0.25, 0.0, 0.25):
                rows.append(_with(
                    seed, f"TREND_EXIT_{threshold:+.2f}",
                    trend_health_exit=threshold,
                ))
        else:
            for direction in ("EXPANDING", "CONTRACTING"):
                rows.append(_with(seed, f"ATR_{direction}", atr_direction=direction))

    elif round_no == 3:
        if symbol in {"SUIUSDC", "UNIUSDC"}:
            level = seed.reentry_atr_level if seed.reentry_atr_level is not None else 0.50
            for direction in ("EXPANDING", "CONTRACTING"):
                rows.append(_with(
                    seed, f"ATR_{direction}_REENTRY_{level:.2f}",
                    atr_direction=direction, reentry_atr_level=level,
                ))
        else:
            max_atr = seed.max_atr_pct if seed.max_atr_pct < 0.9 else 0.03
            min_atr = max(0.0, seed.min_atr_pct)
            min_trend = seed.min_trend_atr if seed.min_trend_atr > -100 else 0.0
            max_trend = seed.max_trend_atr if seed.max_trend_atr < 100 else 3.0
            for atr_mult, trend_shift in ((0.8, -0.15), (0.9, 0.0), (1.1, 0.0), (1.2, 0.15)):
                rows.append(_with(
                    seed,
                    f"LOCAL_REGIME_A{atr_mult:.2f}_T{trend_shift:+.2f}",
                    min_atr_pct=_clamp(min_atr, 0.0, 0.05),
                    max_atr_pct=_clamp(max_atr * atr_mult, 0.008, 0.08),
                    min_trend_atr=_clamp(min_trend + trend_shift, -0.5, 2.0),
                    max_trend_atr=_clamp(max_trend, 0.75, 5.0),
                ))

    elif round_no == 4:
        for floor in (0.0, 0.05, 0.10, 0.20, 0.30):
            rows.append(_with(seed, f"BREAKOUT_{floor:.2f}", min_breakout_atr=floor))

    elif round_no == 5:
        for cap in (1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 999.0):
            if cap > seed.min_trend_atr:
                rows.append(_with(seed, f"TREND_CAP_{cap:g}", max_trend_atr=cap))

    elif round_no == 6:
        for hold in (24, 48, 72, 120, 168):
            rows.append(_with(seed, f"HOLD_{hold}", horizon_hours=hold))

    elif round_no == 7:
        for floor in (0.0, 0.05, 0.10, 0.15, 0.20, 0.30):
            rows.append(_with(seed, f"ENTRY_CMO_{floor:.2f}", min_abs_cmo=floor))

    elif round_no == 8:
        base_max = seed.max_atr_pct if seed.max_atr_pct < 0.9 else 0.03
        floors = sorted({0.0, seed.min_atr_pct, 0.0015, 0.0025, 0.0035})
        caps = sorted({
            _clamp(base_max * 0.75, 0.008, 0.08),
            _clamp(base_max * 0.90, 0.008, 0.08),
            _clamp(base_max, 0.008, 0.08),
            _clamp(base_max * 1.10, 0.008, 0.08),
            _clamp(base_max * 1.25, 0.008, 0.08),
        })
        for lo in floors:
            for hi in caps:
                if lo < hi:
                    rows.append(_with(
                        seed, f"VOL_{lo:.4f}_{hi:.4f}",
                        min_atr_pct=lo, max_atr_pct=hi,
                    ))

    elif round_no == 9:
        for direction in (None, "EXPANDING", "CONTRACTING"):
            for threshold in (-0.50, -0.25, 0.0, 0.25):
                rows.append(_with(
                    seed,
                    f"ATR_{direction or 'ANY'}_EXIT_{threshold:+.2f}",
                    atr_direction=direction, trend_health_exit=threshold,
                ))

    elif round_no == 10:
        if symbol in {"SUIUSDC", "UNIUSDC"}:
            for level in (0.25, 0.50, 0.75, 1.00):
                for threshold in (-0.25, 0.0, 0.25):
                    rows.append(_with(
                        seed,
                        f"REENTRY_{level:.2f}_EXIT_{threshold:+.2f}",
                        reentry_atr_level=level,
                        trend_health_exit=threshold,
                    ))
        else:
            for hold in (48, 72, 120):
                for threshold in (-0.25, 0.0, 0.25):
                    rows.append(_with(
                        seed,
                        f"H{hold}_EXIT_{threshold:+.2f}",
                        horizon_hours=hold,
                        trend_health_exit=threshold,
                    ))

    elif round_no == 11:
        base_min = seed.min_trend_atr if seed.min_trend_atr > -100 else 0.0
        base_max = seed.max_trend_atr if seed.max_trend_atr < 100 else 3.0
        for lo_shift in (-0.25, 0.0, 0.25):
            for hi_shift in (-0.5, 0.0, 0.5):
                lo = _clamp(base_min + lo_shift, -0.5, 2.5)
                hi = _clamp(base_max + hi_shift, 0.75, 5.0)
                if lo < hi:
                    rows.append(_with(
                        seed,
                        f"TREND_WINDOW_{lo:.2f}_{hi:.2f}",
                        min_trend_atr=lo, max_trend_atr=hi,
                    ))

    elif round_no == 12:
        levels = [seed.reentry_atr_level]
        if seed.reentry_atr_level is not None:
            levels += [
                _clamp(seed.reentry_atr_level - 0.25, 0.0, 2.0),
                _clamp(seed.reentry_atr_level + 0.25, 0.0, 2.0),
            ]
        else:
            levels += [0.50]
        exits = [seed.trend_health_exit]
        if seed.trend_health_exit is not None:
            exits += [
                _clamp(seed.trend_health_exit - 0.25, -1.5, 1.0),
                _clamp(seed.trend_health_exit + 0.25, -1.5, 1.0),
            ]
        else:
            exits += [0.0]
        directions = [seed.atr_direction, None]
        for level in levels:
            for exit_threshold in exits:
                for direction in directions:
                    rows.append(_with(
                        seed,
                        f"CONSOLIDATE_R{level}_E{exit_threshold}_D{direction or 'ANY'}",
                        reentry_atr_level=level,
                        trend_health_exit=exit_threshold,
                        atr_direction=direction,
                    ))

    elif round_no == 13:
        for breakout in (0.05, 0.10, 0.20, 0.30):
            for level in (0.25, 0.50, 0.75):
                rows.append(_with(
                    seed,
                    f"BREAKOUT_{breakout:.2f}_REENTRY_{level:.2f}",
                    min_breakout_atr=breakout,
                    reentry_atr_level=level,
                ))

    elif round_no == 14:
        base_max = seed.max_atr_pct if seed.max_atr_pct < 0.9 else 0.03
        for mult in (0.75, 0.90, 1.0, 1.10, 1.25):
            for level in (0.25, 0.50, 0.75):
                rows.append(_with(
                    seed,
                    f"VOL_{mult:.2f}_REENTRY_{level:.2f}",
                    max_atr_pct=_clamp(base_max * mult, 0.008, 0.08),
                    reentry_atr_level=level,
                ))

    elif round_no == 15:
        base_min = seed.min_trend_atr if seed.min_trend_atr > -100 else 0.0
        for lo in sorted({_clamp(base_min + shift, -0.25, 1.5) for shift in (-0.25, 0.0, 0.25, 0.50)}):
            for hi in (1.5, 2.0, 2.5, 3.5):
                if lo < hi:
                    for level in (0.25, 0.50, 0.75):
                        rows.append(_with(
                            seed,
                            f"TREND_{lo:.2f}_{hi:.2f}_REENTRY_{level:.2f}",
                            min_trend_atr=lo,
                            max_trend_atr=hi,
                            reentry_atr_level=level,
                        ))

    elif round_no == 16:
        for cmo in (0.05, 0.10, 0.15, 0.20, 0.30):
            for level in (0.25, 0.50, 0.75):
                rows.append(_with(
                    seed,
                    f"CMO_{cmo:.2f}_REENTRY_{level:.2f}",
                    min_abs_cmo=cmo,
                    reentry_atr_level=level,
                ))

    elif round_no == 17:
        for breakout in (0.05, 0.10, 0.20, 0.30):
            for threshold in (-0.50, -0.25, 0.0, 0.25):
                rows.append(_with(
                    seed,
                    f"BREAKOUT_{breakout:.2f}_EXIT_{threshold:+.2f}",
                    min_breakout_atr=breakout,
                    trend_health_exit=threshold,
                ))

    elif round_no == 18:
        base_max = seed.max_atr_pct if seed.max_atr_pct < 0.9 else 0.03
        for mult in (0.75, 0.90, 1.0, 1.10, 1.25):
            for threshold in (-0.50, -0.25, 0.0, 0.25):
                rows.append(_with(
                    seed,
                    f"VOL_{mult:.2f}_EXIT_{threshold:+.2f}",
                    max_atr_pct=_clamp(base_max * mult, 0.008, 0.08),
                    trend_health_exit=threshold,
                ))

    elif round_no == 19:
        base_min = seed.min_trend_atr if seed.min_trend_atr > -100 else 0.0
        for lo in sorted({_clamp(base_min + shift, -0.25, 1.5) for shift in (-0.25, 0.0, 0.25)}):
            for hi in (1.5, 2.0, 2.5, 3.5):
                if lo < hi:
                    for threshold in (-0.25, 0.0, 0.25):
                        rows.append(_with(
                            seed,
                            f"TREND_{lo:.2f}_{hi:.2f}_EXIT_{threshold:+.2f}",
                            min_trend_atr=lo,
                            max_trend_atr=hi,
                            trend_health_exit=threshold,
                        ))

    elif round_no == 20:
        for cmo in (0.05, 0.10, 0.15, 0.20, 0.30):
            for threshold in (-0.50, -0.25, 0.0, 0.25):
                rows.append(_with(
                    seed,
                    f"CMO_{cmo:.2f}_EXIT_{threshold:+.2f}",
                    min_abs_cmo=cmo,
                    trend_health_exit=threshold,
                ))

    elif round_no == 21:
        for direction in ("EXPANDING", "CONTRACTING"):
            for breakout in (0.05, 0.10, 0.20, 0.30):
                rows.append(_with(
                    seed,
                    f"ATR_{direction}_BREAKOUT_{breakout:.2f}",
                    atr_direction=direction,
                    min_breakout_atr=breakout,
                ))

    elif round_no == 22:
        for direction in ("EXPANDING", "CONTRACTING"):
            for cmo in (0.05, 0.10, 0.15, 0.20, 0.30):
                rows.append(_with(
                    seed,
                    f"ATR_{direction}_CMO_{cmo:.2f}",
                    atr_direction=direction,
                    min_abs_cmo=cmo,
                ))

    elif round_no == 23:
        for hold in (24, 48, 72, 120):
            for level in (0.50, 0.75):
                for threshold in (-0.25, 0.0):
                    rows.append(_with(
                        seed,
                        f"H{hold}_R{level:.2f}_E{threshold:+.2f}",
                        horizon_hours=hold,
                        reentry_atr_level=level,
                        trend_health_exit=threshold,
                    ))

    elif round_no == 24:
        base_max = seed.max_atr_pct if seed.max_atr_pct < 0.9 else 0.03
        max_atrs = sorted({
            _clamp(base_max * 0.90, 0.008, 0.08),
            _clamp(base_max, 0.008, 0.08),
            _clamp(base_max * 1.10, 0.008, 0.08),
        })
        reentries = [seed.reentry_atr_level, 0.50]
        exits = [seed.trend_health_exit, 0.0]
        for max_atr in max_atrs:
            for level in reentries:
                for threshold in exits:
                    rows.append(_with(
                        seed,
                        f"FINAL_PARETO_V{max_atr:.4f}_R{level}_E{threshold}",
                        max_atr_pct=max_atr,
                        reentry_atr_level=level,
                        trend_health_exit=threshold,
                    ))
    elif round_no == 25:
        # New causal axis: point-in-time rank_strength, not searched in rounds 1-24.
        for lo in (-999.0, 0.0, 0.25, 0.50, 0.75, 1.0):
            rows.append(_with(seed, f"RANK_FLOOR_{lo:g}", min_rank_strength=lo))
    elif round_no == 26:
        for lo in (0.0, 0.25, 0.50, 0.75):
            for hi in (1.0, 1.5, 2.0, 3.0, 999.0):
                if lo < hi:
                    rows.append(_with(seed, f"RANK_WINDOW_{lo:g}_{hi:g}", min_rank_strength=lo, max_rank_strength=hi))
    elif round_no == 27:
        for lo in (0.0, 0.25, 0.50, 0.75):
            for hold in (24, 48, 72, 120):
                rows.append(_with(seed, f"RANK_{lo:g}_H{hold}", min_rank_strength=lo, horizon_hours=hold))
    elif round_no == 28:
        base_max = seed.max_atr_pct if seed.max_atr_pct < 0.9 else 0.03
        for lo in (0.0, 0.25, 0.50, 0.75):
            for mult in (0.8, 1.0, 1.2):
                rows.append(_with(seed, f"RANK_{lo:g}_VOL_{mult:.1f}", min_rank_strength=lo, max_atr_pct=_clamp(base_max * mult, 0.008, 0.08)))
    else:
        raise RuntimeError(f"unsupported adaptive round {round_no}")

    return _dedupe(rows)


def _regime(spec: AdaptiveSpec) -> RegimeSpec:
    return RegimeSpec(
        name=spec.name,
        horizon_hours=spec.horizon_hours,
        min_atr_pct=spec.min_atr_pct,
        max_atr_pct=spec.max_atr_pct,
        min_trend_atr=spec.min_trend_atr,
        max_trend_atr=spec.max_trend_atr,
        min_breakout_atr=spec.min_breakout_atr,
        min_abs_cmo=spec.min_abs_cmo,
    )


def _adaptive_entry_filter(spec: AdaptiveSpec):
    base_gate = _entry_filter(_regime(spec))

    def gate(point: IndicatorPoint) -> str | None:
        blocked = base_gate(point)
        if blocked is not None:
            return blocked
        rank = point.rank_strength
        if rank is None:
            if spec.min_rank_strength > -999.0 or spec.max_rank_strength < 999.0:
                return "RANK_STRENGTH_UNAVAILABLE"
            return None
        if rank < spec.min_rank_strength:
            return "RANK_STRENGTH_TOO_LOW"
        if rank > spec.max_rank_strength:
            return "RANK_STRENGTH_TOO_HIGH"
        return None

    return gate


def _run(*, symbol, candles, rules, start, end, costs, params, policy, spec: AdaptiveSpec):
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
        entry_filter_by_symbol={symbol: _adaptive_entry_filter(spec)},
        continuation_reentry_symbols=frozenset(),
        band_reentry_symbols=frozenset(),
        atr_reentry_level_by_symbol=(
            {symbol: float(spec.reentry_atr_level)}
            if spec.reentry_atr_level is not None
            else {}
        ),
        entry_atr_direction_by_symbol=(
            {symbol: spec.atr_direction} if spec.atr_direction else {}
        ),
        trend_health_exit_by_symbol=(
            {symbol: float(spec.trend_health_exit)}
            if spec.trend_health_exit is not None
            else {}
        ),
    )
    return result, events


def _training_metrics(a, b) -> dict:
    pa, pb = D(str(a.metrics.net_pnl)), D(str(b.metrics.net_pnl))
    ha, hb = _position_hours(a), _position_hours(b)
    ppha = pa / ha if ha > 0 else D("-999")
    pphb = pb / hb if hb > 0 else D("-999")
    return {
        "min_pnl": min(pa, pb),
        "sum_pnl": pa + pb,
        "min_trades": min(a.metrics.completed_trades, b.metrics.completed_trades),
        "sum_trades": a.metrics.completed_trades + b.metrics.completed_trades,
        "min_pph": min(ppha, pphb),
        "max_dd": max(D(str(a.metrics.max_drawdown_pct)), D(str(b.metrics.max_drawdown_pct))),
    }


def _choose(rows: list[dict], reference_profit: bool, reference_mature: bool) -> tuple[dict | None, str]:
    eligible = [row for row in rows if row["training_both_positive"]]
    if not eligible:
        return None, "NO_TWO_YEAR_STRESS_POSITIVE_TRAINING_WINNER"

    seed_row = next(row for row in rows if row["candidate"]["name"] == "SEED")
    if reference_profit and not reference_mature and seed_row["training_both_positive"]:
        seed_floor = D(seed_row["training_score"]["min_pnl"]) * TRAINING_PNL_RETENTION_FOR_ACTIVITY
        activity_pool = [
            row for row in eligible
            if D(row["training_score"]["min_pnl"]) >= seed_floor
        ]
        if activity_pool:
            activity_pool.sort(
                key=lambda row: (
                    int(row["training_score"]["min_trades"]),
                    D(row["training_score"]["min_pnl"]),
                    D(row["training_score"]["min_pph"]),
                    -D(row["training_score"]["max_dd"]),
                ),
                reverse=True,
            )
            return activity_pool[0], "ACTIVITY_WITHIN_75PCT_TRAINING_PNL_RETENTION"

    eligible.sort(
        key=lambda row: (
            D(row["training_score"]["min_pnl"]),
            D(row["training_score"]["min_pph"]),
            int(row["training_score"]["min_trades"]),
            D(row["training_score"]["sum_pnl"]),
            -D(row["training_score"]["max_dd"]),
        ),
        reverse=True,
    )
    return eligible[0], "PROFIT_FIRST_TRAINING_SELECTION"


def _classification(reference_row: dict, v_stress, f_stress, profit_ok: bool, mature_ok: bool) -> dict:
    ref = reference_row["reference"]
    ref_val = D(str(ref["validation_stress_net_pnl"]))
    ref_full = D(str(ref["full_3y_stress_net_pnl"]))
    ref_trades = int(ref["full_3y_stress_trades"])
    ref_dd = D(str(ref["full_3y_stress_max_drawdown_pct"]))
    ref_pph = D(str(ref["full_3y_stress_profit_per_position_hour"]))
    ref_profit = bool(reference_row["reference_profitability_pass"])
    ref_mature = bool(reference_row["reference_maturity_pass"])

    cand_val = D(str(v_stress.metrics.net_pnl))
    cand_full = D(str(f_stress.metrics.net_pnl))
    cand_trades = int(f_stress.metrics.completed_trades)
    cand_dd = D(str(f_stress.metrics.max_drawdown_pct))
    hours = _position_hours(f_stress)
    cand_pph = cand_full / hours if hours > 0 else D("-999")

    classification = "UNCHANGED"
    reason = "NO_VALIDATED_IMPROVEMENT"

    if profit_ok and not ref_profit:
        classification = "IMPROVED"
        reason = "BECAME_ROBUSTLY_PROFITABLE"
    elif profit_ok and ref_profit:
        strict = (
            cand_val >= ref_val
            and cand_full >= ref_full
            and cand_dd <= ref_dd + D("1.0")
            and (
                cand_val > ref_val
                or cand_full > ref_full
                or cand_trades > ref_trades
                or cand_pph > ref_pph
                or cand_dd < ref_dd
            )
        )
        maturity_tradeoff = (
            mature_ok and not ref_mature
            and cand_val >= ref_val * D("0.75")
            and cand_full >= ref_full * D("0.75")
            and cand_dd <= ref_dd + D("5.0")
            and cand_pph >= ref_pph * D("0.60")
        )
        if strict:
            classification = "IMPROVED"
            reason = "ROBUST_DOMINANCE"
        elif maturity_tradeoff:
            classification = "IMPROVED"
            reason = "MATURE_FILLER_TRADEOFF_WITH_BOUNDED_PNL_RETENTION"
    elif not ref_profit and not profit_ok:
        benchmark_better = (
            cand_val > ref_val
            and cand_full >= ref_full * D("0.80")
            and cand_dd <= ref_dd + D("5.0")
        )
        if benchmark_better:
            classification = "IMPROVED"
            reason = "RESEARCH_BENCHMARK_MOVED_TOWARD_VALIDATION"

    if (
        cand_val < ref_val
        and cand_full < ref_full
        and cand_dd > ref_dd
    ):
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
        "candidate_reference": {
            "validation_stress_net_pnl": str(cand_val),
            "validation_stress_trades": v_stress.metrics.completed_trades,
            "full_3y_stress_net_pnl": str(cand_full),
            "full_3y_stress_trades": cand_trades,
            "full_3y_stress_max_drawdown_pct": str(cand_dd),
            "full_3y_stress_profit_per_position_hour": str(cand_pph),
        },
    }


def main() -> None:
    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    round_no = int(control["round"])
    max_rounds = int(control["max_rounds"])
    if not 1 <= round_no <= max_rounds:
        raise RuntimeError(f"invalid adaptive round {round_no}/{max_rounds}")

    start, end = _canonical_window()
    train_a_end = start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    validation_start = train_b_end
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))["per_symbol"]

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol: dict[str, dict] = {}
    improved: list[str] = []
    profitability_pass: list[str] = []
    mature: list[str] = []
    technical_family = control["family_sequence"][round_no - 1]

    for symbol in SATELLITES:
        row = state["per_symbol"][symbol]
        if bool(row["reference_maturity_pass"]):
            per_symbol[symbol] = {
                "status": "FROZEN_MATURE_INCUMBENT",
                "classification": "UNCHANGED",
                "reason": "MATURE_INCUMBENT_PROTECTED",
                "reference": row["reference"],
                "training_seed": row["training_seed"],
            }
            profitability_pass.append(symbol)
            mature.append(symbol)
            continue

        params = StrategyParameters(**row["parameters"])
        policy = TradePolicy(**row["policy"])
        rules = _rules(client, symbol)
        warmup = params.warmup_bars
        proxy_symbol = str(sources[symbol]["history_source_for_training"])
        proxy = _adapt(
            client.fetch_klines(proxy_symbol, start=start - warmup * BAR, end_exclusive=end),
            symbol,
        )
        direct = client.fetch_klines(
            symbol, start=validation_start - warmup * BAR, end_exclusive=end
        )

        candidates: list[dict] = []
        for spec in _variants(symbol, _seed(row), round_no):
            ta, _ = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=start, end=train_a_end, costs=STRESS_COSTS,
                params=params, policy=policy, spec=spec,
            )
            tb, _ = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=train_a_end, end=train_b_end, costs=STRESS_COSTS,
                params=params, policy=policy, spec=spec,
            )
            tm = _training_metrics(ta, tb)
            candidates.append({
                "candidate": asdict(spec),
                "training_both_positive": _positive(ta) and _positive(tb),
                "training_score": {key: str(value) for key, value in tm.items()},
                "train_a_stress": _payload(ta),
                "train_b_stress": _payload(tb),
            })

        winner, selection_mode = _choose(
            candidates,
            bool(row["reference_profitability_pass"]),
            bool(row["reference_maturity_pass"]),
        )
        if winner is None:
            per_symbol[symbol] = {
                "status": "NO_TRAINING_WINNER",
                "classification": "UNCHANGED",
                "reason": selection_mode,
                "training_candidates": candidates,
                "training_winner": None,
                "reference": row["reference"],
                "training_seed": row["training_seed"],
            }
            continue

        spec = AdaptiveSpec(**winner["candidate"])
        v_base, _ = _run(
            symbol=symbol, candles=direct, rules=rules,
            start=validation_start, end=end, costs=BASELINE_COSTS,
            params=params, policy=policy, spec=spec,
        )
        v_stress, _ = _run(
            symbol=symbol, candles=direct, rules=rules,
            start=validation_start, end=end, costs=STRESS_COSTS,
            params=params, policy=policy, spec=spec,
        )
        f_base, _ = _run(
            symbol=symbol, candles=proxy, rules=rules,
            start=start, end=end, costs=BASELINE_COSTS,
            params=params, policy=policy, spec=spec,
        )
        f_stress, _ = _run(
            symbol=symbol, candles=proxy, rules=rules,
            start=start, end=end, costs=STRESS_COSTS,
            params=params, policy=policy, spec=spec,
        )

        profit_ok = all(_positive(x) for x in (v_base, v_stress, f_base, f_stress))
        mature_ok = profit_ok and f_stress.metrics.completed_trades >= MIN_MATURE_CYCLES
        if profit_ok:
            profitability_pass.append(symbol)
        if mature_ok:
            mature.append(symbol)

        delta = _classification(row, v_stress, f_stress, profit_ok, mature_ok)
        if delta["classification"] == "IMPROVED":
            improved.append(symbol)

        per_symbol[symbol] = {
            "status": "TRAINING_WINNER_VALIDATED",
            "family": technical_family,
            "selection_mode": selection_mode,
            "training_candidates": candidates,
            "training_winner": winner,
            "validation": {
                "baseline": _payload(v_base),
                "stress": _payload(v_stress),
                "full_3y_proxy_baseline": _payload(f_base),
                "full_3y_proxy_stress": _payload(f_stress),
            },
            "profitability_pass": profit_ok,
            "maturity_pass": mature_ok,
            "reference": row["reference"],
            "reference_source_run": row["reference_source_run"],
            "economic_delta_vs_reference": delta,
            "classification": delta["classification"],
            "reason": delta["reason"],
        }

    result = {
        "schema_version": 1,
        "study": "SATELLITE_ISOLATED_5X250_ADAPTIVE_CYCLE",
        "round": round_no,
        "max_rounds": max_rounds,
        "family": technical_family,
        "capital_per_market_usdc": "250",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": state["protected_product_sha"],
        "per_symbol": per_symbol,
        "improved_symbols": improved,
        "profitability_pass_symbols": profitability_pass,
        "mature_symbols": mature,
        "economic_progress": bool(improved),
        "target_count": 5,
        "selection_contract": {
            "training_only_selects_next_seed": True,
            "validation_rejection_only": True,
            "two_independent_training_years_stress_positive_required": True,
            "activity_search_requires_75pct_training_pnl_retention": True,
            "validated_reference_separate_from_training_seed": True,
            "green_workflow_is_not_economic_progress": True,
        },
        "next_stage": (
            "SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY"
            if len(mature) == 5
            else "SATELLITE_ISOLATED_5X250_ADAPTIVE_CYCLE"
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
        "family": technical_family,
        "improved_symbols": improved,
        "profitability_pass_symbols": profitability_pass,
        "mature_symbols": mature,
        "economic_progress": result["economic_progress"],
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()

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
TRAINING_PNL_RETENTION_FOR_ACTIVITY = D("0.90")


@dataclass(frozen=True, slots=True)
class AdaptiveSpec:
    name: str
    horizon_hours: int = 0
    min_atr_pct: float = 0.0
    max_atr_pct: float = 1.0
    min_trend_atr: float = -999.0
    max_trend_atr: float = 999.0
    min_breakout_atr: float = 0.0
    max_breakout_atr: float = 999.0
    min_abs_cmo: float = 0.0
    reentry_atr_level: float | None = None
    atr_direction: str | None = None
    trend_health_exit: float | None = None
    min_rank_strength: float = -999.0
    max_rank_strength: float = 999.0
    # Optional candidate-level TradePolicy overrides. These remain point-in-time:
    # they only alter entry gates computed from information available on the
    # current/previous closed bars.
    policy_cmo_floor: float | None = None
    policy_slope_bars: int | None = None
    policy_stop_atr: float | None = None
    policy_trail_atr: float | None = None
    strategy_vidya_length: int | None = None
    strategy_momentum_length: int | None = None
    strategy_smoothing_length: int | None = None
    strategy_atr_length: int | None = None
    strategy_band_multiplier: float | None = None


def _seed(row: dict) -> AdaptiveSpec:
    return AdaptiveSpec(**row["training_seed"])


def _reference_seed(row: dict) -> AdaptiveSpec:
    return AdaptiveSpec(**row.get("reference_seed", row["training_seed"]))


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
            row.max_breakout_atr, row.min_abs_cmo, row.reentry_atr_level, row.atr_direction,
            row.trend_health_exit, row.min_rank_strength, row.max_rank_strength,
            row.policy_cmo_floor, row.policy_slope_bars,
            row.policy_stop_atr, row.policy_trail_atr,
            row.strategy_vidya_length, row.strategy_momentum_length,
            row.strategy_smoothing_length, row.strategy_atr_length,
            row.strategy_band_multiplier,
        )
        if key not in seen:
            seen.add(key)
            out.append(row)
    return tuple(out)


def _variants(
    symbol: str,
    seed: AdaptiveSpec,
    round_no: int,
    reference_seed: AdaptiveSpec | None = None,
) -> tuple[AdaptiveSpec, ...]:
    rows: list[AdaptiveSpec] = [_with(seed, "SEED")]
    if reference_seed is not None:
        rows.append(_with(reference_seed, "REFERENCE_ANCHOR"))

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
    elif round_no == 29:
        # New causal axis after R28 exhaustion: reject point-in-time overextended breakouts.
        # breakout_strength is computed at the decision candle; no future/holdout input.
        for hi in (0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 999.0):
            if seed.min_breakout_atr < hi:
                rows.append(_with(seed, f"BREAKOUT_CAP_{hi:g}", max_breakout_atr=hi))
    elif round_no == 30:
        for lo in (0.0, 0.05, 0.10, 0.20, 0.30):
            for hi in (0.50, 0.75, 1.00, 1.50, 2.00):
                if lo < hi:
                    rows.append(_with(seed, f"BREAKOUT_WINDOW_{lo:g}_{hi:g}", min_breakout_atr=lo, max_breakout_atr=hi))
    elif round_no == 31:
        for hi in (0.50, 0.75, 1.00, 1.50, 2.00):
            for hold in (24, 48, 72, 120):
                rows.append(_with(seed, f"BREAKOUT_CAP_{hi:g}_H{hold}", max_breakout_atr=hi, horizon_hours=hold))
    elif round_no == 32:
        for hi in (0.50, 0.75, 1.00, 1.50, 2.00):
            for rank_lo in (0.0, 0.25, 0.50, 0.75):
                rows.append(_with(seed, f"BREAKOUT_CAP_{hi:g}_RANK_{rank_lo:g}", max_breakout_atr=hi, min_rank_strength=rank_lo))
    elif round_no == 33:
        # Manual causal repair after repeated post-R24 failures:
        # restart each search from the last accepted reference as a stable anchor,
        # then explore bounded symbol-specific neighborhoods. This prevents a
        # rejected TRAINING seed from dragging later rounds away from a proven
        # incumbent while keeping all candidate generation TRAINING-only.
        anchor = reference_seed or seed
        if symbol == "SUIUSDC":
            for max_atr in (0.0125, 0.0150, 0.0175, 0.0200):
                for cmo in (0.0, 0.05, 0.10):
                    rows.append(_with(
                        anchor,
                        f"REF_SUI_V{max_atr:.4f}_C{cmo:.2f}",
                        horizon_hours=0,
                        max_atr_pct=max_atr,
                        min_abs_cmo=cmo,
                        reentry_atr_level=None,
                        trend_health_exit=None,
                        min_rank_strength=-999.0,
                        max_rank_strength=999.0,
                        max_breakout_atr=999.0,
                    ))
            for level in (0.15, 0.25, 0.35):
                rows.append(_with(
                    anchor,
                    f"REF_SUI_REENTRY_{level:.2f}",
                    horizon_hours=0,
                    reentry_atr_level=level,
                    trend_health_exit=None,
                    min_rank_strength=-999.0,
                    max_rank_strength=999.0,
                    max_breakout_atr=999.0,
                ))
        elif symbol == "UNIUSDC":
            for cmo in (0.05, 0.10, 0.15):
                for level in (0.25, 0.375, 0.50):
                    rows.append(_with(
                        anchor,
                        f"REF_UNI_C{cmo:.3f}_R{level:.3f}",
                        horizon_hours=0,
                        min_abs_cmo=cmo,
                        reentry_atr_level=level,
                        trend_health_exit=None,
                        min_rank_strength=-999.0,
                        max_rank_strength=999.0,
                        max_breakout_atr=999.0,
                    ))
            for hold in (48, 72, 120):
                for level in (0.25, 0.50):
                    rows.append(_with(
                        anchor,
                        f"REF_UNI_H{hold}_R{level:.2f}",
                        horizon_hours=hold,
                        reentry_atr_level=level,
                        min_rank_strength=-999.0,
                        max_rank_strength=999.0,
                        max_breakout_atr=999.0,
                    ))
        elif symbol == "AAVEUSDC":
            regimes = (
                (0.0030, 0.0180, 0.25, 1.75),
                (0.0030, 0.0225, 0.25, 2.00),
                (0.0050, 0.0200, 0.50, 2.00),
                (0.0050, 0.0250, 0.50, 2.50),
                (0.0075, 0.0225, 0.75, 2.00),
                (0.0075, 0.0250, 0.75, 2.50),
            )
            for lo_atr, hi_atr, lo_trend, hi_trend in regimes:
                for cmo in (0.0, 0.10, 0.20):
                    for hold in (120, 168):
                        rows.append(_with(
                            anchor,
                            f"REF_AAVE_A{lo_atr:.4f}_{hi_atr:.4f}_T{lo_trend:.2f}_{hi_trend:.2f}_C{cmo:.2f}_H{hold}",
                            horizon_hours=hold,
                            min_atr_pct=lo_atr,
                            max_atr_pct=hi_atr,
                            min_trend_atr=lo_trend,
                            max_trend_atr=hi_trend,
                            min_abs_cmo=cmo,
                            reentry_atr_level=None,
                            min_rank_strength=-999.0,
                            max_rank_strength=999.0,
                            max_breakout_atr=999.0,
                        ))
        elif symbol == "BCHUSDC":
            for max_atr in (0.0125, 0.0150, 0.0175, 0.0200):
                for cmo in (0.05, 0.10, 0.15, 0.20):
                    for trend_lo in (0.0, 0.25):
                        rows.append(_with(
                            anchor,
                            f"REF_BCH_V{max_atr:.4f}_C{cmo:.2f}_T{trend_lo:.2f}",
                            horizon_hours=0,
                            max_atr_pct=max_atr,
                            min_trend_atr=trend_lo,
                            max_trend_atr=2.50,
                            min_abs_cmo=cmo,
                            reentry_atr_level=None,
                            min_rank_strength=-999.0,
                            max_rank_strength=999.0,
                            max_breakout_atr=999.0,
                        ))
    elif round_no == 34:
        # Symbol-specific repair from run #193 TRAINING evidence.
        # NEAR is frozen before this function is called.
        # SUI: increase opportunity count without repeating rejected ATR-reentry.
        # UNI: vary the actual slope/CMO policy gate, which was fixed at slope=72.
        # AAVE: preserve the improved R33 anchor while testing entry/exit quality.
        # BCH: isolate point-in-time CMO/direction/horizon quality without the
        # overly restrictive trend floor that produced zero-trade candidates.
        anchor = reference_seed or seed
        if symbol == "SUIUSDC":
            for policy_cmo in (0.30, 0.35, 0.40, 0.45):
                rows.append(_with(
                    anchor,
                    f"R34_SUI_POLICY_CMO_{policy_cmo:.2f}",
                    horizon_hours=0,
                    reentry_atr_level=None,
                    trend_health_exit=None,
                    policy_cmo_floor=policy_cmo,
                    policy_slope_bars=0,
                ))
            for policy_cmo in (0.35, 0.40):
                for hold in (48, 72, 120):
                    rows.append(_with(
                        anchor,
                        f"R34_SUI_CMO_{policy_cmo:.2f}_H{hold}",
                        horizon_hours=hold,
                        reentry_atr_level=None,
                        trend_health_exit=None,
                        policy_cmo_floor=policy_cmo,
                        policy_slope_bars=0,
                    ))
            for exit_threshold in (-0.50, -0.25, 0.0):
                rows.append(_with(
                    anchor,
                    f"R34_SUI_EXIT_{exit_threshold:+.2f}",
                    horizon_hours=0,
                    reentry_atr_level=None,
                    trend_health_exit=exit_threshold,
                    policy_cmo_floor=0.40,
                    policy_slope_bars=0,
                ))

        elif symbol == "UNIUSDC":
            # The incumbent policy has slope_bars=72. Test whether 24/0 releases
            # additional valid entries while the 90%-PnL-retention gate protects
            # the incumbent economics.
            for slope in (0, 24, 72):
                for policy_cmo in (0.20, 0.25, 0.30, 0.35):
                    rows.append(_with(
                        anchor,
                        f"R34_UNI_SLOPE{slope}_CMO{policy_cmo:.2f}",
                        horizon_hours=0,
                        policy_slope_bars=slope,
                        policy_cmo_floor=policy_cmo,
                    ))

        elif symbol == "AAVEUSDC":
            for direction in (None, "EXPANDING", "CONTRACTING"):
                for policy_cmo in (0.20, 0.30, 0.40):
                    rows.append(_with(
                        anchor,
                        f"R34_AAVE_{direction or 'ANY'}_CMO{policy_cmo:.2f}",
                        atr_direction=direction,
                        policy_cmo_floor=policy_cmo,
                        policy_slope_bars=0,
                    ))
            for exit_threshold in (-0.50, -0.25, 0.0):
                for hold in (96, 120, 144):
                    rows.append(_with(
                        anchor,
                        f"R34_AAVE_H{hold}_EXIT{exit_threshold:+.2f}",
                        horizon_hours=hold,
                        trend_health_exit=exit_threshold,
                        policy_cmo_floor=0.30,
                        policy_slope_bars=0,
                    ))
            for cap in (0.75, 1.00, 1.50, 2.00):
                rows.append(_with(
                    anchor,
                    f"R34_AAVE_BREAKOUT_CAP_{cap:.2f}",
                    max_breakout_atr=cap,
                    policy_cmo_floor=0.30,
                    policy_slope_bars=0,
                ))

        elif symbol == "BCHUSDC":
            for direction in (None, "EXPANDING", "CONTRACTING"):
                for policy_cmo in (0.00, 0.05, 0.10, 0.15, 0.20):
                    rows.append(_with(
                        anchor,
                        f"R34_BCH_{direction or 'ANY'}_CMO{policy_cmo:.2f}",
                        atr_direction=direction,
                        policy_cmo_floor=policy_cmo,
                        policy_slope_bars=0,
                        min_trend_atr=-999.0,
                        max_trend_atr=999.0,
                    ))
            for hold in (48, 72, 120):
                for policy_cmo in (0.05, 0.10, 0.15):
                    rows.append(_with(
                        anchor,
                        f"R34_BCH_H{hold}_CMO{policy_cmo:.2f}",
                        horizon_hours=hold,
                        policy_cmo_floor=policy_cmo,
                        policy_slope_bars=0,
                        min_trend_atr=-999.0,
                        max_trend_atr=999.0,
                    ))

    elif round_no == 35:
        # Material-challenger repair after run #198. Every generated row differs
        # from the accepted reference; SEED/REFERENCE_ANCHOR remain floors only.
        anchor = reference_seed or seed
        if symbol == "SUIUSDC":
            for stop in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_SUI_STOP_{stop:.2f}",
                    horizon_hours=0, reentry_atr_level=None,
                    trend_health_exit=None, policy_stop_atr=stop,
                    policy_trail_atr=None,
                ))
            for trail in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_SUI_TRAIL_{trail:.2f}",
                    horizon_hours=0, reentry_atr_level=None,
                    trend_health_exit=None, policy_stop_atr=None,
                    policy_trail_atr=trail,
                ))
        elif symbol == "UNIUSDC":
            for stop in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_UNI_STOP_{stop:.2f}",
                    policy_cmo_floor=0.30, policy_slope_bars=72,
                    policy_stop_atr=stop, policy_trail_atr=None,
                ))
            for trail in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_UNI_TRAIL_{trail:.2f}",
                    policy_cmo_floor=0.30, policy_slope_bars=72,
                    policy_stop_atr=None, policy_trail_atr=trail,
                ))
            for hold in (48, 72, 120):
                for stop in (1.50, 2.00):
                    rows.append(_with(
                        anchor, f"R35_UNI_H{hold}_STOP{stop:.2f}",
                        horizon_hours=hold,
                        policy_cmo_floor=0.30, policy_slope_bars=72,
                        policy_stop_atr=stop, policy_trail_atr=None,
                    ))
        elif symbol == "AAVEUSDC":
            for stop in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_AAVE_STOP_{stop:.2f}",
                    policy_cmo_floor=0.30, policy_slope_bars=0,
                    policy_stop_atr=stop, policy_trail_atr=None,
                ))
            for trail in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_AAVE_TRAIL_{trail:.2f}",
                    policy_cmo_floor=0.30, policy_slope_bars=0,
                    policy_stop_atr=None, policy_trail_atr=trail,
                ))
            for hold in (72, 96, 144):
                for stop in (1.50, 2.00):
                    rows.append(_with(
                        anchor, f"R35_AAVE_H{hold}_STOP{stop:.2f}",
                        horizon_hours=hold,
                        policy_cmo_floor=0.30, policy_slope_bars=0,
                        policy_stop_atr=stop, policy_trail_atr=None,
                    ))
        elif symbol == "BCHUSDC":
            for stop in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_BCH_STOP_{stop:.2f}",
                    policy_cmo_floor=0.0, policy_slope_bars=0,
                    policy_stop_atr=stop, policy_trail_atr=None,
                ))
            for trail in (1.25, 1.50, 2.00, 2.50):
                rows.append(_with(
                    anchor, f"R35_BCH_TRAIL_{trail:.2f}",
                    policy_cmo_floor=0.0, policy_slope_bars=0,
                    policy_stop_atr=None, policy_trail_atr=trail,
                ))
            for hold in (48, 72, 96):
                for stop in (1.50, 2.00):
                    rows.append(_with(
                        anchor, f"R35_BCH_H{hold}_STOP{stop:.2f}",
                        horizon_hours=hold,
                        policy_cmo_floor=0.0, policy_slope_bars=0,
                        policy_stop_atr=stop, policy_trail_atr=None,
                    ))

    elif round_no == 36:
        # Base-strategy neighborhood repair for symbols whose policy/regime
        # neighborhoods are exhausted. All parameters remain causal and
        # point-in-time; selection is TRAINING-only.
        anchor = reference_seed or seed
        if symbol == "SUIUSDC":
            for vidya in (12, 15, 18):
                for band in (2.15, 2.30, 2.45):
                    rows.append(_with(
                        anchor, f"R36_SUI_V{vidya}_B{band:.2f}_STOP2.50",
                        policy_stop_atr=2.50,
                        strategy_vidya_length=vidya,
                        strategy_band_multiplier=band,
                    ))
        elif symbol == "UNIUSDC":
            for vidya in (10, 12, 14):
                for smooth in (8, 10, 12):
                    rows.append(_with(
                        anchor, f"R36_UNI_V{vidya}_S{smooth}",
                        strategy_vidya_length=vidya,
                        strategy_smoothing_length=smooth,
                        policy_cmo_floor=0.30,
                        policy_slope_bars=72,
                    ))
            for band in (1.80, 2.00, 2.20):
                rows.append(_with(
                    anchor, f"R36_UNI_B{band:.2f}",
                    strategy_band_multiplier=band,
                    policy_cmo_floor=0.30,
                    policy_slope_bars=72,
                ))
        elif symbol == "AAVEUSDC":
            for vidya in (8, 10, 12):
                for band in (1.80, 2.00, 2.20):
                    rows.append(_with(
                        anchor, f"R36_AAVE_V{vidya}_B{band:.2f}",
                        strategy_vidya_length=vidya,
                        strategy_band_multiplier=band,
                        policy_cmo_floor=0.30,
                        policy_slope_bars=0,
                        policy_stop_atr=2.00,
                    ))
        elif symbol == "BCHUSDC":
            for vidya in (10, 13, 16):
                for band in (2.80, 3.20, 3.60):
                    rows.append(_with(
                        anchor, f"R36_BCH_V{vidya}_B{band:.2f}",
                        strategy_vidya_length=vidya,
                        strategy_band_multiplier=band,
                        policy_cmo_floor=0.0,
                        policy_slope_bars=0,
                    ))
            for momentum in (12, 16, 20):
                rows.append(_with(
                    anchor, f"R36_BCH_M{momentum}",
                    strategy_momentum_length=momentum,
                    policy_cmo_floor=0.0,
                    policy_slope_bars=0,
                ))

    elif round_no == 37:
        # Manual final gap-filler refinement from Round-36 TRAINING evidence.
        # Search is deliberately local around accepted references / strongest
        # training neighbors. Validation remains rejection-only.
        anchor = reference_seed or seed

        if symbol == "SUIUSDC":
            # Interpolate between the accepted V15/B2.30 reference and the
            # strong but validation-weak V12/B2.15 training challenger.
            for vidya in (13, 14, 15):
                for band in (2.20, 2.25, 2.30):
                    for stop in (2.25, 2.50):
                        rows.append(_with(
                            anchor,
                            f"R37_SUI_V{vidya}_B{band:.2f}_STOP{stop:.2f}",
                            strategy_vidya_length=vidya,
                            strategy_band_multiplier=band,
                            policy_stop_atr=stop,
                        ))

        elif symbol == "UNIUSDC":
            # Avoid the failed 72->24 jump. Test moderate slope relaxation plus
            # small CMO/reentry adjustments to release more entries while the
            # 90%-training-PnL activity floor protects economics.
            for slope in (48, 60, 72):
                for policy_cmo in (0.25, 0.30):
                    for abs_cmo in (0.10, 0.15):
                        for reentry in (0.40, 0.50):
                            rows.append(_with(
                                anchor,
                                f"R37_UNI_S{slope}_PC{policy_cmo:.2f}_AC{abs_cmo:.2f}_R{reentry:.2f}",
                                policy_slope_bars=slope,
                                policy_cmo_floor=policy_cmo,
                                min_abs_cmo=abs_cmo,
                                reentry_atr_level=reentry,
                            ))

        elif symbol == "AAVEUSDC":
            # Already robustly profitable and close to maturity (140 vs 157
            # trades). Search shorter occupancy / stop combinations around the
            # accepted R35 stop-2.00 reference.
            for hold in (72, 96, 108, 120):
                for stop in (1.50, 1.75, 2.00, 2.25):
                    rows.append(_with(
                        anchor,
                        f"R37_AAVE_H{hold}_STOP{stop:.2f}",
                        horizon_hours=hold,
                        policy_stop_atr=stop,
                        policy_cmo_floor=0.30,
                        policy_slope_bars=0,
                    ))

        elif symbol == "BCHUSDC":
            # R36 V10/B3.20 nearly repaired the worst training fold but failed
            # validation. Combine that structure with volatility-state and
            # momentum controls to suppress the unstable regime rather than
            # merely increasing trade count.
            for momentum in (12, 16):
                for atr_cap in (0.0125, 0.0150, 0.0175, 0.0200):
                    for direction in (None, "EXPANDING", "CONTRACTING"):
                        rows.append(_with(
                            anchor,
                            f"R37_BCH_M{momentum}_A{atr_cap:.4f}_{direction or 'ANY'}",
                            strategy_vidya_length=10,
                            strategy_momentum_length=momentum,
                            strategy_band_multiplier=3.20,
                            max_atr_pct=atr_cap,
                            atr_direction=direction,
                            policy_cmo_floor=0.0,
                            policy_slope_bars=0,
                        ))

    else:
        # Durable post-registry generator: exhaustion is not a terminal state.
        # Every generation changes a bounded point-in-time interaction grid derived
        # only from the TRAINING seed. Validation/holdout data never enters here.
        generation = round_no - 32
        breakout_caps = tuple(round(v, 3) for v in (
            0.45 + 0.05 * (generation % 5),
            0.80 + 0.10 * (generation % 4),
            1.25 + 0.15 * (generation % 3),
        ))
        rank_floors = tuple(round(v, 3) for v in (
            0.10 * (generation % 4),
            0.25 + 0.10 * (generation % 5),
            0.60 + 0.05 * (generation % 4),
        ))
        holds = (24 + 12 * (generation % 3), 48 + 24 * (generation % 4), 96 + 24 * (generation % 5))
        for hi in breakout_caps:
            for rank_lo in rank_floors:
                for hold in holds:
                    if seed.min_breakout_atr < hi:
                        rows.append(_with(
                            seed,
                            f"AUTO_G{generation}_BC{hi:g}_R{rank_lo:g}_H{hold}",
                            max_breakout_atr=hi,
                            min_rank_strength=rank_lo,
                            horizon_hours=hold,
                        ))

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
        breakout = point.breakout_strength
        if breakout is None:
            if spec.max_breakout_atr < 999.0:
                return "BREAKOUT_STRENGTH_UNAVAILABLE"
            return None
        if breakout > spec.max_breakout_atr:
            return "BREAKOUT_STRENGTH_TOO_HIGH"
        return None

    return gate


def _run(*, symbol, candles, rules, start, end, costs, params, policy, spec: AdaptiveSpec):
    effective_params = replace(
        params,
        vidya_length=(spec.strategy_vidya_length if spec.strategy_vidya_length is not None else params.vidya_length),
        momentum_length=(spec.strategy_momentum_length if spec.strategy_momentum_length is not None else params.momentum_length),
        smoothing_length=(spec.strategy_smoothing_length if spec.strategy_smoothing_length is not None else params.smoothing_length),
        atr_length=(spec.strategy_atr_length if spec.strategy_atr_length is not None else params.atr_length),
        band_multiplier=(spec.strategy_band_multiplier if spec.strategy_band_multiplier is not None else params.band_multiplier),
    )
    effective_policy = replace(
        policy,
        cmo_floor=(
            float(spec.policy_cmo_floor)
            if spec.policy_cmo_floor is not None
            else policy.cmo_floor
        ),
        slope_bars=(
            int(spec.policy_slope_bars)
            if spec.policy_slope_bars is not None
            else policy.slope_bars
        ),
        stop_atr=(
            float(spec.policy_stop_atr)
            if spec.policy_stop_atr is not None
            else policy.stop_atr
        ),
        trail_atr=(
            float(spec.policy_trail_atr)
            if spec.policy_trail_atr is not None
            else policy.trail_atr
        ),
    )
    result, events = run_filler_router_portfolio(
        candles_by_symbol={symbol: candles},
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=CAPITAL,
        target_notional=CAPITAL,
        slot_count=1,
        costs=costs,
        execution_rules={symbol: rules},
        strategy_parameters_by_symbol={symbol: effective_params},
        trade_policies_by_symbol={symbol: effective_policy},
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


def _training_metrics(a, b, folds) -> dict:
    pa, pb = D(str(a.metrics.net_pnl)), D(str(b.metrics.net_pnl))
    ha, hb = _position_hours(a), _position_hours(b)
    ppha = pa / ha if ha > 0 else D("-999")
    pphb = pb / hb if hb > 0 else D("-999")
    fold_pnls = [D(str(result.metrics.net_pnl)) for result in folds]
    fold_trades = [int(result.metrics.completed_trades) for result in folds]
    return {
        "min_pnl": min(pa, pb),
        "sum_pnl": pa + pb,
        "min_trades": min(a.metrics.completed_trades, b.metrics.completed_trades),
        "sum_trades": a.metrics.completed_trades + b.metrics.completed_trades,
        "min_pph": min(ppha, pphb),
        "max_dd": max(D(str(a.metrics.max_drawdown_pct)), D(str(b.metrics.max_drawdown_pct))),
        "fold_positive_count": sum(1 for pnl in fold_pnls if pnl > 0),
        "worst_fold_pnl": min(fold_pnls),
        "median_fold_pnl": D(str(statistics.median(fold_pnls))),
        "fold_trade_floor": min(fold_trades),
    }


def _same_training_behavior(a: dict, b: dict) -> bool:
    # Different labels/explicit overrides can still resolve to the exact same
    # effective strategy/policy. Do not count those as a new hypothesis.
    return (
        a.get("training_score") == b.get("training_score")
        and a.get("train_a_stress") == b.get("train_a_stress")
        and a.get("train_b_stress") == b.get("train_b_stress")
        and a.get("training_fold_stress") == b.get("training_fold_stress")
    )


def _choose(
    rows: list[dict],
    reference_profit: bool,
    reference_mature: bool,
    *,
    require_material_challenger: bool = False,
) -> tuple[dict | None, str]:
    eligible = [row for row in rows if row["training_both_positive"]]
    if not eligible:
        return None, "NO_TWO_YEAR_STRESS_POSITIVE_TRAINING_WINNER"

    stable = [
        row for row in eligible
        if int(row["training_score"].get("fold_positive_count", 0)) >= 3
    ]
    pool = stable or eligible
    seed_row = next(row for row in rows if row["candidate"]["name"] == "SEED")
    anchor_row = next(
        (row for row in rows if row["candidate"]["name"] == "REFERENCE_ANCHOR"),
        None,
    )
    floor_row = (
        anchor_row
        if anchor_row is not None and anchor_row["training_both_positive"]
        else seed_row
    )
    if require_material_challenger:
        challengers = [
            row for row in pool
            if row["candidate"]["name"] not in {"SEED", "REFERENCE_ANCHOR"}
            and not _same_training_behavior(row, floor_row)
        ]
        if challengers:
            pool = challengers
        else:
            return None, "NO_MATERIAL_TRAINING_CHALLENGER"
    if reference_profit and not reference_mature and floor_row["training_both_positive"]:
        pnl_floor = (
            D(floor_row["training_score"]["min_pnl"])
            * TRAINING_PNL_RETENTION_FOR_ACTIVITY
        )
        activity_pool = [
            row for row in pool
            if D(row["training_score"]["min_pnl"]) >= pnl_floor
        ]
        if activity_pool:
            activity_pool.sort(
                key=lambda row: (
                    int(row["training_score"].get("fold_positive_count", 0)),
                    int(row["training_score"]["min_trades"]),
                    D(row["training_score"].get("worst_fold_pnl", "-999999")),
                    D(row["training_score"]["min_pnl"]),
                    D(row["training_score"]["min_pph"]),
                    -D(row["training_score"]["max_dd"]),
                ),
                reverse=True,
            )
            return activity_pool[0], "REFERENCE_ANCHORED_STABLE_ACTIVITY_90PCT_PNL"

    pool.sort(
        key=lambda row: (
            int(row["training_score"].get("fold_positive_count", 0)),
            D(row["training_score"].get("worst_fold_pnl", "-999999")),
            D(row["training_score"]["min_pnl"]),
            D(row["training_score"]["min_pph"]),
            -D(row["training_score"]["max_dd"]),
            int(row["training_score"]["min_trades"]),
            D(row["training_score"]["sum_pnl"]),
        ),
        reverse=True,
    )
    return pool[0], "FOLD_STABILITY_PROFIT_FIRST_TRAINING_SELECTION"


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
        filler_efficiency_tradeoff = (
            cand_val > ref_val
            and cand_full >= ref_full * D("0.99")
            and cand_trades > ref_trades
            and cand_dd < ref_dd
            and cand_pph > ref_pph
        )
        if strict:
            classification = "IMPROVED"
            reason = "ROBUST_DOMINANCE"
        elif filler_efficiency_tradeoff:
            classification = "IMPROVED"
            reason = "FILLER_EFFICIENCY_TRADEOFF_99PCT_PNL_RETENTION"
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
    family_sequence = list(control.get("family_sequence") or [])
    if round_no <= len(family_sequence):
        technical_family = family_sequence[round_no - 1]
    else:
        # Post-registry rounds are generated dynamically. Do not index past the
        # finite registry merely to label the evidence payload.
        generation = round_no - 32
        technical_family = (
            f"GENERATED_POST_REGISTRY_G{generation}_BREAKOUT_RANK_HORIZON"
        )

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
        fold_bounds = (
            (start, start + timedelta(days=182)),
            (start + timedelta(days=182), train_a_end),
            (train_a_end, train_a_end + timedelta(days=182)),
            (train_a_end + timedelta(days=182), train_b_end),
        )
        for spec in _variants(symbol, _seed(row), round_no, _reference_seed(row)):
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
            folds = []
            for fold_start, fold_end in fold_bounds:
                fold_result, _ = _run(
                    symbol=symbol, candles=proxy, rules=rules,
                    start=fold_start, end=fold_end, costs=STRESS_COSTS,
                    params=params, policy=policy, spec=spec,
                )
                folds.append(fold_result)
            tm = _training_metrics(ta, tb, folds)
            candidates.append({
                "candidate": asdict(spec),
                "training_both_positive": _positive(ta) and _positive(tb),
                "training_score": {key: str(value) for key, value in tm.items()},
                "train_a_stress": _payload(ta),
                "train_b_stress": _payload(tb),
                "training_fold_stress": [_payload(result) for result in folds],
            })

        winner, selection_mode = _choose(
            candidates,
            bool(row["reference_profitability_pass"]),
            bool(row["reference_maturity_pass"]),
            require_material_challenger=round_no >= 35,
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
            "activity_search_requires_90pct_reference_training_pnl_retention": True,
            "post_round_32_requires_half_year_fold_stability": True,
            "reference_anchor_is_always_in_candidate_pool": True,
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

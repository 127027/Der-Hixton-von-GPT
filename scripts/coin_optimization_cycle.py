"""Coin-by-coin V6 research cycle with mandatory shared-portfolio recheck.

Research only: this module never mutates the active strategy, Paper account or
runtime settings. Candidate ranking uses training windows only. A bounded Top-K
shortlist is frozen before validation; validation/full-window evidence may reject
finalists but never introduce an unranked replacement. Robust finalists are then
tested one-at-a-time in the canonical max-budget portfolio before compatible combinations.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.engine import run_isolated_batch, run_single_backtest
from hixton.backtest.models import (
    BASELINE_COSTS,
    STRESS_COSTS,
    BacktestResult,
    CostModel,
    ExecutionRules,
)
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.binance import BinancePublicClient
from hixton.domain.capital import DEFAULT_MAX_CAPITAL_USDC, capital_plan
from hixton.domain.models import Candle, StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

D = Decimal


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    parameters: StrategyParameters
    policy: TradePolicy


def _payload(candidate: Candidate) -> dict[str, object]:
    return {
        "parameters": asdict(candidate.parameters),
        "trade_policy": asdict(candidate.policy),
    }


def _candidate_hash(candidate: Candidate) -> str:
    raw = json.dumps(_payload(candidate), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


MAX_ADAPTIVE_GENERATIONS = 3
ADAPTIVE_ANCHORS_PER_SYMBOL = 2
MISSION_FROZEN_PROMOTED_SYMBOLS = frozenset({"ADAUSDC", "DOTUSDC"})


def _candidate_from_payload(name: str, payload: dict[str, object]) -> Candidate:
    """Rebuild a research candidate from previously emitted evidence."""

    parameters_raw = payload.get("parameters")
    policy_raw = payload.get("trade_policy")
    if not isinstance(parameters_raw, dict) or not isinstance(policy_raw, dict):
        raise ValueError(f"{name}: malformed candidate payload")
    parameters = StrategyParameters(
        vidya_length=int(parameters_raw["vidya_length"]),
        momentum_length=int(parameters_raw["momentum_length"]),
        smoothing_length=int(parameters_raw["smoothing_length"]),
        atr_length=int(parameters_raw["atr_length"]),
        band_multiplier=float(parameters_raw["band_multiplier"]),
        warmup_bars=int(parameters_raw["warmup_bars"]),
    )
    policy = TradePolicy(
        cmo_floor=float(policy_raw["cmo_floor"]),
        slope_bars=int(policy_raw["slope_bars"]),
        stop_atr=float(policy_raw["stop_atr"]),
        trail_atr=float(policy_raw["trail_atr"]),
    )
    return Candidate(name=name, parameters=parameters, policy=policy)


def _adaptive_candidates_from_previous(
    symbol: str,
    previous_evidence: dict[str, object],
    generation: int,
) -> tuple[Candidate, ...]:
    """Build the next bounded neighbourhood from prior TRAINING-ranked evidence only.

    Accepted profiles are carried forward unchanged (frozen). For unresolved coins,
    new candidates are symmetric local perturbations around the prior training Top-K.
    Validation/full-window and portfolio outcomes never choose a new direction.
    """

    per_coin = previous_evidence.get("per_coin")
    if not isinstance(per_coin, dict):
        return ()
    coin = per_coin.get(symbol)
    if not isinstance(coin, dict):
        return ()

    accepted_profile = coin.get("accepted_profile")
    if coin.get("accepted") is True and isinstance(accepted_profile, dict):
        return (
            _candidate_from_payload(
                f"g{generation}_frozen_{coin.get('accepted_candidate_name', 'winner')}",
                accepted_profile,
            ),
        )

    shortlist = coin.get("training_top_k_challengers")
    finalists = coin.get("finalists")
    if not isinstance(shortlist, list) or not isinstance(finalists, dict):
        return ()

    radius = max(1, min(generation, 3))
    vidya_step = radius
    momentum_step = radius
    smoothing_step = radius
    atr_step = 15 * radius
    band_step = round(0.05 * radius, 2)
    cmo_step = round(0.05 * radius, 2)

    generated: list[Candidate] = []
    seen: set[tuple[StrategyParameters, TradePolicy]] = set()

    def add(candidate: Candidate) -> None:
        identity = (candidate.parameters, candidate.policy)
        if identity in seen:
            return
        seen.add(identity)
        generated.append(candidate)

    for anchor_index, raw_name in enumerate(shortlist[:ADAPTIVE_ANCHORS_PER_SYMBOL]):
        name = str(raw_name)
        finalist = finalists.get(name)
        if not isinstance(finalist, dict):
            continue
        profile = finalist.get("profile")
        if not isinstance(profile, dict):
            continue
        anchor = _candidate_from_payload(f"g{generation}_a{anchor_index}_{name}", profile)
        add(anchor)

        p = anchor.parameters
        policy = anchor.policy
        prefix = f"g{generation}_a{anchor_index}"

        for sign, suffix in ((-1, "m"), (1, "p")):
            add(
                Candidate(
                    f"{prefix}_vidya_{suffix}{vidya_step}",
                    replace(p, vidya_length=max(2, p.vidya_length + sign * vidya_step)),
                    policy,
                )
            )
            add(
                Candidate(
                    f"{prefix}_mom_{suffix}{momentum_step}",
                    replace(
                        p,
                        momentum_length=max(4, p.momentum_length + sign * momentum_step),
                    ),
                    policy,
                )
            )
            add(
                Candidate(
                    f"{prefix}_smooth_{suffix}{smoothing_step}",
                    replace(
                        p,
                        smoothing_length=max(2, p.smoothing_length + sign * smoothing_step),
                    ),
                    policy,
                )
            )
            add(
                Candidate(
                    f"{prefix}_atr_{suffix}{atr_step}",
                    replace(p, atr_length=max(15, min(240, p.atr_length + sign * atr_step))),
                    policy,
                )
            )
            add(
                Candidate(
                    f"{prefix}_band_{suffix}{int(band_step * 100):02d}",
                    replace(
                        p,
                        band_multiplier=max(
                            0.5,
                            round(p.band_multiplier + sign * band_step, 2),
                        ),
                    ),
                    policy,
                )
            )
            add(
                Candidate(
                    f"{prefix}_cmo_{suffix}{int(cmo_step * 100):02d}",
                    p,
                    replace(
                        policy,
                        cmo_floor=max(
                            0.0,
                            min(1.0, round(policy.cmo_floor + sign * cmo_step, 2)),
                        ),
                    ),
                )
            )
            add(
                Candidate(
                    f"{prefix}_mom_smooth_{suffix}",
                    replace(
                        p,
                        momentum_length=max(4, p.momentum_length + sign * momentum_step),
                        smoothing_length=max(2, p.smoothing_length + sign * smoothing_step),
                    ),
                    policy,
                )
            )
            add(
                Candidate(
                    f"{prefix}_vidya_band_{suffix}",
                    replace(
                        p,
                        vidya_length=max(2, p.vidya_length + sign * vidya_step),
                        band_multiplier=max(
                            0.5,
                            round(p.band_multiplier + sign * band_step, 2),
                        ),
                    ),
                    policy,
                )
            )

    return tuple(generated)


def candidate_catalog(symbol: str) -> tuple[Candidate, ...]:
    """Return a frozen, bounded neighbourhood around the active coin profile."""

    definition = V6_COIN_STRATEGY
    base_parameters = definition.parameters_for(symbol)
    base_policy = definition.policy_for(symbol)
    candidates: list[Candidate] = []
    seen: set[tuple[StrategyParameters, TradePolicy]] = set()

    def add(
        name: str,
        *,
        parameters: StrategyParameters | None = None,
        policy: TradePolicy | None = None,
    ) -> None:
        candidate = Candidate(
            name=name,
            parameters=parameters or base_parameters,
            policy=policy or base_policy,
        )
        identity = (candidate.parameters, candidate.policy)
        if identity in seen:
            return
        seen.add(identity)
        candidates.append(candidate)

    add("current")

    for floor in (0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4):
        add(f"cmo{int(floor * 100):02d}", policy=replace(base_policy, cmo_floor=floor))
    for bars in (0, 24, 72):
        add(f"slope{bars}", policy=replace(base_policy, slope_bars=bars))
    for stop in (0.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5):
        add(
            f"stop{str(stop).replace('.', '_')}",
            policy=replace(base_policy, stop_atr=stop),
        )
    for trail in (0.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5):
        add(
            f"trail{str(trail).replace('.', '_')}",
            policy=replace(base_policy, trail_atr=trail),
        )

    add(
        "cmo20_slope24",
        policy=replace(
            base_policy,
            cmo_floor=max(0.2, base_policy.cmo_floor),
            slope_bars=24,
        ),
    )
    add(
        "cmo20_stop2",
        policy=replace(base_policy, cmo_floor=max(0.2, base_policy.cmo_floor), stop_atr=2.0),
    )
    add(
        "cmo20_trail3",
        policy=replace(base_policy, cmo_floor=max(0.2, base_policy.cmo_floor), trail_atr=3.0),
    )
    add(
        "slope72_stop2",
        policy=replace(base_policy, slope_bars=72, stop_atr=2.0),
    )
    add(
        "slope24_stop2",
        policy=replace(base_policy, slope_bars=24, stop_atr=2.0),
    )
    add(
        "slope24_trail4",
        policy=replace(base_policy, slope_bars=24, trail_atr=4.0),
    )

    for length in (4, 6, 8, 10, 12):
        add(f"vidya{length}", parameters=replace(base_parameters, vidya_length=length))
    for length in (14, 20, 28):
        add(
            f"momentum{length}",
            parameters=replace(base_parameters, momentum_length=length),
        )
    for length in (6, 8, 12, 15, 20):
        add(
            f"smoothing{length}",
            parameters=replace(base_parameters, smoothing_length=length),
        )
    for length in (30, 60, 90, 120, 180):
        add(f"atr{length}", parameters=replace(base_parameters, atr_length=length))

    # Evidence-led fine neighbourhood. These values deliberately sit between the
    # established coarse candidates so promising isolated improvements can be
    # tested for a portfolio-compatible compromise without weakening any gate.
    for length in (5, 7, 9, 11):
        add(f"vidya{length}", parameters=replace(base_parameters, vidya_length=length))
    for length in (16, 18, 22, 24):
        add(
            f"momentum{length}",
            parameters=replace(base_parameters, momentum_length=length),
        )
    for length in (45, 75, 105, 150):
        add(f"atr{length}", parameters=replace(base_parameters, atr_length=length))

    for suffix, offset in (
        ("minus_02", -0.2),
        ("minus_01", -0.1),
        ("plus_01", 0.1),
        ("plus_02", 0.2),
        ("plus_04", 0.4),
        ("plus_05", 0.5),
    ):
        add(
            f"band_{suffix}",
            parameters=replace(
                base_parameters,
                band_multiplier=max(0.5, round(base_parameters.band_multiplier + offset, 2)),
            ),
        )

    for suffix, offset in (
        ("minus_06", -0.6),
        ("minus_03", -0.3),
        ("plus_03", 0.3),
        ("plus_06", 0.6),
    ):
        add(
            f"band_{suffix}",
            parameters=replace(
                base_parameters,
                band_multiplier=max(0.5, round(base_parameters.band_multiplier + offset, 2)),
            ),
        )

    add(
        "vidya8_band_plus_03",
        parameters=replace(
            base_parameters,
            vidya_length=8,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "vidya10_band_plus_03",
        parameters=replace(
            base_parameters,
            vidya_length=10,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "atr90_band_plus_03",
        parameters=replace(
            base_parameters,
            atr_length=90,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "atr120_band_plus_03",
        parameters=replace(
            base_parameters,
            atr_length=120,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "smoothing12_band_plus_03",
        parameters=replace(
            base_parameters,
            smoothing_length=12,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )

    # Structured two-parameter neighbourhood around the active coin profile.
    # These are still generated solely from the isolated coin profile; the shared
    # The canonical max-budget portfolio is used only later as a compatibility check.
    vidya_near = sorted(
        {
            max(2, base_parameters.vidya_length - 2),
            base_parameters.vidya_length + 2,
        }
    )
    momentum_near = sorted({
        max(4, base_parameters.momentum_length - 2),
        base_parameters.momentum_length + 2,
    })
    smoothing_near = sorted({
        max(2, base_parameters.smoothing_length - 2),
        base_parameters.smoothing_length + 2,
    })
    atr_near = sorted({
        max(15, base_parameters.atr_length - 30),
        min(180, base_parameters.atr_length + 30),
    })
    for offset in (-0.1, 0.1, 0.2):
        band = max(0.5, round(base_parameters.band_multiplier + offset, 2))
        suffix = str(offset).replace("-", "m").replace(".", "_")
        for length in vidya_near:
            add(
                f"vidya{length}_band_{suffix}",
                parameters=replace(
                    base_parameters,
                    vidya_length=length,
                    band_multiplier=band,
                ),
            )
        for length in momentum_near:
            add(
                f"momentum{length}_band_{suffix}",
                parameters=replace(
                    base_parameters,
                    momentum_length=length,
                    band_multiplier=band,
                ),
            )
    for length in smoothing_near:
        add(
            f"smoothing{length}_momentum{momentum_near[0]}",
            parameters=replace(
                base_parameters,
                smoothing_length=length,
                momentum_length=momentum_near[0],
            ),
        )
    for length in atr_near:
        add(
            f"atr{length}_momentum{momentum_near[0]}",
            parameters=replace(
                base_parameters,
                atr_length=length,
                momentum_length=momentum_near[0],
            ),
        )

    # Stage-2 local neighbourhoods are fixed from prior TRAINING rankings only.
    # They deliberately interpolate around training leaders without consulting the
    # independent validation/full-window outcome for candidate discovery.
    if symbol == "BTCUSDC":
        for smoothing in (9, 10, 11):
            for offset in (0.2, 0.3):
                add(
                    f"local_smooth{smoothing}_band_p{int(offset * 100):02d}",
                    parameters=replace(
                        base_parameters,
                        smoothing_length=smoothing,
                        band_multiplier=round(base_parameters.band_multiplier + offset, 2),
                    ),
                )
        add(
            "local_atr135_band_p03",
            parameters=replace(
                base_parameters,
                atr_length=135,
                band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
            ),
        )
        add(
            "local_vidya4_smooth10",
            parameters=replace(base_parameters, vidya_length=4, smoothing_length=10),
        )

    elif symbol == "ETHUSDC":
        for smoothing, momentum in ((5, 18), (6, 19), (7, 18), (7, 19)):
            add(
                f"local_smooth{smoothing}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    smoothing_length=smoothing,
                    momentum_length=momentum,
                ),
            )
        for atr, momentum in ((45, 18), (45, 19), (30, 19)):
            add(
                f"local_atr{atr}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    atr_length=atr,
                    momentum_length=momentum,
                ),
            )
        for slope, smoothing, momentum in (
            (0, 6, 20),
            (0, 8, 18),
            (0, 6, 18),
        ):
            add(
                f"local_slope{slope}_smooth{smoothing}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    smoothing_length=smoothing,
                    momentum_length=momentum,
                ),
                policy=replace(base_policy, slope_bars=slope),
            )

    elif symbol == "BNBUSDC":
        for vidya, momentum in ((9, 18), (9, 19)):
            add(
                f"local_vidya{vidya}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    vidya_length=vidya,
                    momentum_length=momentum,
                ),
            )
        for vidya, atr in ((9, 135), (9, 150)):
            add(
                f"local_vidya{vidya}_atr{atr}",
                parameters=replace(
                    base_parameters,
                    vidya_length=vidya,
                    atr_length=atr,
                ),
            )
        for atr, momentum in ((135, 18), (135, 19), (150, 19)):
            add(
                f"local_atr{atr}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    atr_length=atr,
                    momentum_length=momentum,
                ),
            )
        for smoothing, momentum in ((7, 18), (7, 19)):
            add(
                f"local_smooth{smoothing}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    smoothing_length=smoothing,
                    momentum_length=momentum,
                ),
            )
        add(
            "local_mom17",
            parameters=replace(base_parameters, momentum_length=17),
        )

    elif symbol == "SOLUSDC":
        for momentum, smoothing in ((18, 12), (18, 13), (19, 12), (19, 13)):
            add(
                f"local_mom{momentum}_smooth{smoothing}",
                parameters=replace(
                    base_parameters,
                    momentum_length=momentum,
                    smoothing_length=smoothing,
                ),
            )

    elif symbol == "XRPUSDC":
        for momentum in (21, 23):
            add(
                f"local_mom{momentum}",
                parameters=replace(base_parameters, momentum_length=momentum),
            )
        for momentum, offset in ((22, -0.05), (22, 0.05), (21, 0.05), (23, 0.05)):
            suffix = "m05" if offset < 0 else "p05"
            add(
                f"local_mom{momentum}_band_{suffix}",
                parameters=replace(
                    base_parameters,
                    momentum_length=momentum,
                    band_multiplier=round(base_parameters.band_multiplier + offset, 2),
                ),
            )

    elif symbol == "ADAUSDC":
        for vidya in (7, 8, 9):
            add(
                f"local_vidya{vidya}_mom14",
                parameters=replace(
                    base_parameters,
                    vidya_length=vidya,
                    momentum_length=14,
                ),
            )
        for vidya, offset in ((8, -0.05), (8, 0.05), (9, -0.05)):
            suffix = "m05" if offset < 0 else "p05"
            add(
                f"local_vidya{vidya}_band_{suffix}",
                parameters=replace(
                    base_parameters,
                    vidya_length=vidya,
                    band_multiplier=round(base_parameters.band_multiplier + offset, 2),
                ),
            )

    elif symbol == "LINKUSDC":
        for momentum in (21, 23):
            add(
                f"local_mom{momentum}",
                parameters=replace(base_parameters, momentum_length=momentum),
            )
        for momentum, offset in ((22, -0.05), (22, 0.05), (23, -0.05), (23, 0.05)):
            suffix = "m05" if offset < 0 else "p05"
            add(
                f"local_mom{momentum}_band_{suffix}",
                parameters=replace(
                    base_parameters,
                    momentum_length=momentum,
                    band_multiplier=round(base_parameters.band_multiplier + offset, 2),
                ),
            )
        for vidya, momentum in ((9, 22), (10, 22), (11, 22), (9, 23)):
            add(
                f"local_vidya{vidya}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    vidya_length=vidya,
                    momentum_length=momentum,
                ),
            )

    elif symbol == "AVAXUSDC":
        for momentum in (21, 23):
            add(
                f"local_mom{momentum}",
                parameters=replace(base_parameters, momentum_length=momentum),
            )
        for vidya in (8, 9, 10, 11):
            add(
                f"local_vidya{vidya}_mom22",
                parameters=replace(
                    base_parameters,
                    vidya_length=vidya,
                    momentum_length=22,
                ),
            )
        for vidya in (9, 10):
            for offset in (0.1, 0.2):
                add(
                    f"local_vidya{vidya}_band_p{int(offset * 100):02d}",
                    parameters=replace(
                        base_parameters,
                        vidya_length=vidya,
                        band_multiplier=round(base_parameters.band_multiplier + offset, 2),
                    ),
                )

    elif symbol == "DOTUSDC":
        for vidya in (5, 7):
            for offset in (-0.05, 0.05, 0.1, 0.15, 0.2):
                suffix = (
                    f"m{abs(int(offset * 100)):02d}"
                    if offset < 0
                    else f"p{int(offset * 100):02d}"
                )
                add(
                    f"local_vidya{vidya}_band_{suffix}",
                    parameters=replace(
                        base_parameters,
                        vidya_length=vidya,
                        band_multiplier=round(base_parameters.band_multiplier + offset, 2),
                    ),
                )
        for offset in (-0.05, 0.05):
            suffix = "m05" if offset < 0 else "p05"
            add(
                f"local_vidya8_band_{suffix}",
                parameters=replace(
                    base_parameters,
                    vidya_length=8,
                    band_multiplier=round(base_parameters.band_multiplier + offset, 2),
                ),
            )
        for vidya in (7, 8):
            add(
                f"local_vidya{vidya}_cmo20",
                parameters=replace(base_parameters, vidya_length=vidya),
                policy=replace(base_policy, cmo_floor=0.2),
            )

    elif symbol == "DOGEUSDC":
        for smoothing, momentum in (
            (16, 16),
            (18, 16),
            (17, 15),
            (17, 17),
            (16, 17),
            (18, 15),
        ):
            add(
                f"local_smooth{smoothing}_mom{momentum}",
                parameters=replace(
                    base_parameters,
                    smoothing_length=smoothing,
                    momentum_length=momentum,
                ),
            )

    return tuple(candidates)


def rank_training_candidates(
    scores: dict[str, tuple[Decimal, Decimal, Decimal]],
    *,
    limit: int = 5,
) -> tuple[str, ...]:
    """Freeze an ordered Top-K from stress-only train A/B evidence."""

    if limit <= 0:
        raise ValueError("training shortlist limit must be positive")
    ordered = sorted(
        scores,
        key=lambda name: (
            min(scores[name][0], scores[name][1]),
            scores[name][0] + scores[name][1],
            -scores[name][2],
            name == "current",
            name,
        ),
        reverse=True,
    )
    return tuple(ordered[:limit])



def _training_behavior_key(result: BacktestResult) -> tuple[object, ...]:
    """Fingerprint observable training behaviour, not parameter identity."""

    trades = tuple(
        (
            trade.entry_time_utc.isoformat(),
            trade.exit_time_utc.isoformat(),
            trade.entry_signal_id,
            trade.exit_signal_id,
            str(trade.realized_pnl),
        )
        for trade in result.trades
    )
    return (
        str(result.metrics.return_pct),
        str(result.metrics.max_drawdown_pct),
        trades,
    )


def freeze_distinct_training_shortlist(
    ordered: tuple[str, ...],
    behavior_keys: dict[str, tuple[object, ...]],
    *,
    limit: int = 8,
    current_name: str = "current",
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Freeze Top-K unique training behaviours without consulting holdout data."""

    if limit <= 0:
        raise ValueError("training shortlist limit must be positive")
    if current_name not in behavior_keys:
        raise KeyError(current_name)
    chosen: list[str] = []
    skipped: list[str] = []
    seen = {behavior_keys[current_name]}
    for name in ordered:
        if name == current_name:
            continue
        behavior = behavior_keys[name]
        if behavior in seen:
            skipped.append(name)
            continue
        seen.add(behavior)
        chosen.append(name)
        if len(chosen) == limit:
            break
    return tuple(chosen), tuple(skipped)


def choose_training_candidate(
    scores: dict[str, tuple[Decimal, Decimal, Decimal]],
) -> str:
    """Compatibility helper: return the first frozen training-ranked candidate."""

    return rank_training_candidates(scores, limit=1)[0]


def _passes_coin_gate(
    *,
    current_base: BacktestResult,
    current_stress: BacktestResult,
    challenger_base: BacktestResult,
    challenger_stress: BacktestResult,
    full_current: BacktestResult,
    full_current_stress: BacktestResult,
    full_challenger: BacktestResult,
    full_challenger_stress: BacktestResult,
) -> bool:
    cb = current_base.metrics
    cs = current_stress.metrics
    xb = challenger_base.metrics
    xs = challenger_stress.metrics
    fcb = full_current.metrics
    fcs = full_current_stress.metrics
    fxb = full_challenger.metrics
    fxs = full_challenger_stress.metrics
    return (
        xb.return_pct >= cb.return_pct
        and xs.return_pct >= cs.return_pct
        and (xb.return_pct > cb.return_pct or xs.return_pct > cs.return_pct)
        and xb.max_drawdown_pct <= cb.max_drawdown_pct + D("5")
        and xs.max_drawdown_pct <= cs.max_drawdown_pct + D("5")
        and fxb.return_pct >= fcb.return_pct
        and fxs.return_pct >= fcs.return_pct
        and (fxb.return_pct > fcb.return_pct or fxs.return_pct > fcs.return_pct)
    )


def _loss_signal_clusters(result: BacktestResult) -> dict[str, object]:
    """Summarize losing-entry conditions from immutable signal/trade evidence."""

    signal_by_id = {signal.signal_id: signal for signal in result.signals}
    volatility = {"ATR_LT_1PCT": 0, "ATR_1_TO_2PCT": 0, "ATR_GE_2PCT": 0}
    breakout = {"LT_0_5": 0, "0_5_TO_1": 0, "GE_1": 0, "MISSING": 0}
    holding = {"LE_24H": 0, "25_TO_72H": 0, "GT_72H": 0}
    examples: list[dict[str, object]] = []
    losses = [trade for trade in result.trades if trade.realized_pnl < 0]
    for trade in losses:
        signal = signal_by_id.get(trade.entry_signal_id)
        if signal is not None and signal.close > 0:
            atr_pct = D(str(signal.atr)) / D(str(signal.close)) * D("100")
            if atr_pct < D("1"):
                volatility["ATR_LT_1PCT"] += 1
            elif atr_pct < D("2"):
                volatility["ATR_1_TO_2PCT"] += 1
            else:
                volatility["ATR_GE_2PCT"] += 1
            strength = signal.breakout_strength
            if strength is None:
                breakout["MISSING"] += 1
            elif strength < 0.5:
                breakout["LT_0_5"] += 1
            elif strength < 1.0:
                breakout["0_5_TO_1"] += 1
            else:
                breakout["GE_1"] += 1
        hours = trade.holding_hours
        if hours <= D("24"):
            holding["LE_24H"] += 1
        elif hours <= D("72"):
            holding["25_TO_72H"] += 1
        else:
            holding["GT_72H"] += 1
    for trade in sorted(losses, key=lambda item: item.realized_pnl)[:10]:
        signal = signal_by_id.get(trade.entry_signal_id)
        examples.append(
            {
                "entry_utc": trade.entry_time_utc.isoformat(),
                "exit_utc": trade.exit_time_utc.isoformat(),
                "pnl": str(trade.realized_pnl),
                "return_pct": str(trade.realized_return_pct),
                "holding_hours": str(trade.holding_hours),
                "entry_signal": (
                    None
                    if signal is None
                    else {
                        "close": signal.close,
                        "atr": signal.atr,
                        "atr_pct_of_close": (
                            None
                            if signal.close <= 0
                            else str(D(str(signal.atr)) / D(str(signal.close)) * D("100"))
                        ),
                        "upper": signal.upper,
                        "lower": signal.lower,
                        "breakout_strength": signal.breakout_strength,
                        "point_index": signal.point_index,
                    }
                ),
            }
        )
    return {
        "losing_trades": len(losses),
        "volatility_regime_proxy": volatility,
        "breakout_strength_proxy": breakout,
        "holding_time_clusters": holding,
        "worst_loss_examples": examples,
        "limitations": (
            "Signal evidence exposes ATR/bands/breakout strength but not CMO/VIDYA snapshots; "
            "those require deterministic point reconstruction for a deeper follow-up."
        ),
    }


def _rules() -> dict[str, ExecutionRules]:
    public = BinancePublicClient(base_url="https://data-api.binance.vision")
    result: dict[str, ExecutionRules] = {}
    for symbol in V6_COIN_STRATEGY.symbols:
        saved = public.symbol_rules(symbol)
        if not saved.tradable_for_quote("USDC"):
            raise RuntimeError(f"{symbol}: current Binance USDC rules are not tradable")
        result[symbol] = ExecutionRules(
            tick_size=saved.tick_size,
            step_size=saved.step_size,
            min_qty=saved.min_qty,
            min_notional=saved.min_notional,
        )
    return result


def _blocked_reason_counts(items: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = item.rsplit(":", 1)[-1]
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _blocked_counts(result: BacktestResult) -> dict[str, int]:
    return _blocked_reason_counts(result.blocked_signals)


def _worst_losses(result: BacktestResult, limit: int = 5) -> list[dict[str, object]]:
    losses = sorted(
        (trade for trade in result.trades if trade.realized_pnl < 0),
        key=lambda trade: trade.realized_pnl,
    )[:limit]
    return [
        {
            "entry_utc": trade.entry_time_utc.isoformat(),
            "exit_utc": trade.exit_time_utc.isoformat(),
            "pnl": str(trade.realized_pnl),
            "return_pct": str(trade.realized_return_pct),
            "holding_hours": str(trade.holding_hours),
            "entry_price": str(trade.entry_price),
            "exit_price": str(trade.exit_price),
        }
        for trade in losses
    ]


def _result_summary(result: BacktestResult) -> dict[str, object]:
    metrics = result.metrics
    return {
        "ending_equity": str(metrics.ending_equity),
        "return_pct": str(metrics.return_pct),
        "completed_trades": metrics.completed_trades,
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "win_rate_pct": None if metrics.win_rate_pct is None else str(metrics.win_rate_pct),
        "profit_factor": None if metrics.profit_factor is None else str(metrics.profit_factor),
        "average_win": None if metrics.average_win is None else str(metrics.average_win),
        "average_loss": None if metrics.average_loss is None else str(metrics.average_loss),
        "max_drawdown_pct": str(metrics.max_drawdown_pct),
        "average_holding_hours": (
            None if metrics.average_holding_hours is None else str(metrics.average_holding_hours)
        ),
        "blocked_reasons": _blocked_counts(result),
        "worst_losses": _worst_losses(result),
    }


def _run_single(
    *,
    symbol: str,
    candles: list[Candle],
    rules: ExecutionRules,
    start: datetime,
    end: datetime,
    candidate: Candidate,
    costs: CostModel,
    version: str,
) -> BacktestResult:
    return run_single_backtest(
        symbol=symbol,
        candles=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=D("250"),
        target_notional=D("250"),
        costs=costs,
        execution_rules=rules,
        strategy_parameters=candidate.parameters,
        trade_policy=candidate.policy,
        strategy_semantics=V6_COIN_STRATEGY.semantics,
        strategy_version=version,
    )


def _profile_hashes(profiles: dict[str, Candidate]) -> dict[str, str]:
    return {symbol: _candidate_hash(candidate) for symbol, candidate in profiles.items()}


def _runner_profile_hashes(
    parameters_by_symbol: dict[str, StrategyParameters],
    policies_by_symbol: dict[str, TradePolicy],
) -> dict[str, str]:
    if set(parameters_by_symbol) != set(policies_by_symbol):
        raise RuntimeError("runner parameter/policy symbol sets diverged")
    return {
        symbol: hashlib.sha256(
            json.dumps(
                {
                    "parameters": asdict(parameters_by_symbol[symbol]),
                    "trade_policy": asdict(policies_by_symbol[symbol]),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        for symbol in parameters_by_symbol
    }


def _batch_summary(batch: Any) -> dict[str, object]:
    return {
        "starting_equity": str(batch.starting_equity),
        "ending_equity": str(batch.ending_equity),
        "net_pnl": str(batch.net_pnl),
        "return_pct": str(batch.return_pct),
        "completed_trades": batch.completed_trades,
        "max_drawdown_pct": str(batch.max_drawdown_pct),
        "per_symbol": {
            result.symbol: _result_summary(result)
            for result in batch.results
        },
    }


def _portfolio_summary(result: Any) -> dict[str, object]:
    by_symbol: dict[str, dict[str, int | str]] = {}
    for trade in result.trades:
        item = by_symbol.setdefault(
            trade.symbol,
            {"position_cycles": 0, "slot_trades": 0, "realized_pnl": "0"},
        )
        item["position_cycles"] = int(item["position_cycles"]) + 1
        item["slot_trades"] = int(item["slot_trades"]) + trade.slot_count
        item["realized_pnl"] = str(D(str(item["realized_pnl"])) + trade.realized_pnl)
    return {
        "ending_equity": str(result.metrics.ending_equity),
        "return_pct": str(result.metrics.return_pct),
        "position_cycles": result.metrics.completed_trades,
        "slot_trades": result.metrics.completed_slot_trades,
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "risk_halted_at_utc": (
            None if result.risk_halted_at_utc is None else result.risk_halted_at_utc.isoformat()
        ),
        "blocked_reasons": _blocked_reason_counts(result.blocked_signals),
        "per_symbol": dict(sorted(by_symbol.items())),
    }


def aggregate_promotion_gate(
    batches: dict[str, dict[str, object]],
    portfolios: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Require the assembled candidate to preserve both canonical report models."""

    checks = {
        "isolated_baseline": (
            D(str(batches["current_baseline"]["ending_equity"])),
            D(str(batches["candidate_baseline"]["ending_equity"])),
        ),
        "isolated_stress": (
            D(str(batches["current_stress"]["ending_equity"])),
            D(str(batches["candidate_stress"]["ending_equity"])),
        ),
        "portfolio_baseline": (
            D(str(portfolios["current_baseline"]["ending_equity"])),
            D(str(portfolios["candidate_baseline"]["ending_equity"])),
        ),
        "portfolio_stress": (
            D(str(portfolios["current_stress"]["ending_equity"])),
            D(str(portfolios["candidate_stress"]["ending_equity"])),
        ),
    }
    non_regressive = all(candidate >= current for current, candidate in checks.values())
    improved = any(candidate > current for current, candidate in checks.values())
    return {
        "promotable": non_regressive and improved,
        "non_regressive": non_regressive,
        "improved": improved,
        "checks": {
            name: {
                "current_ending_equity": str(current),
                "candidate_ending_equity": str(candidate),
                "delta": str(candidate - current),
                "passes": candidate >= current,
            }
            for name, (current, candidate) in checks.items()
        },
    }


def run_cycle(
    output: Path,
    *,
    previous_evidence: dict[str, object] | None = None,
    generation: int = 0,
) -> dict[str, object]:
    definition = V6_COIN_STRATEGY
    _, report_start, report_end = safe_closed_window()
    rules = _rules()
    history = load_continuity_history(
        strategy=definition,
        report_start_utc=report_start,
        report_end_utc=report_end,
        execution_rules=rules,
    )
    candles = history.candles_by_symbol

    train_a_end = report_start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    if train_b_end >= report_end - timedelta(days=120):
        raise RuntimeError("three-year window does not leave a meaningful validation period")
    windows = {
        "train_a": (report_start, train_a_end),
        "train_b": (train_a_end, train_b_end),
        "validation": (train_b_end, report_end),
        "full": (report_start, report_end),
    }

    catalog_by_symbol: dict[str, dict[str, Candidate]] = {}
    for symbol in definition.symbols:
        base_catalog = {
            candidate.name: candidate for candidate in candidate_catalog(symbol)
        }
        if symbol in MISSION_FROZEN_PROMOTED_SYMBOLS:
            catalog_by_symbol[symbol] = {"current": base_catalog["current"]}
            continue
        if previous_evidence is None:
            catalog_by_symbol[symbol] = base_catalog
            continue

        adaptive = _adaptive_candidates_from_previous(
            symbol,
            previous_evidence,
            generation,
        )
        previous_per_coin = previous_evidence.get("per_coin")
        previous_coin = (
            previous_per_coin.get(symbol)
            if isinstance(previous_per_coin, dict)
            else None
        )

        # Once a candidate has cleared the independent coin gate and the canonical
        # portfolio gate in an earlier generation, freeze that coin for the rest
        # of this research run. It is still revalidated against the same immutable
        # three-year window, but no new parameters are searched for that symbol.
        if (
            isinstance(previous_coin, dict)
            and previous_coin.get("accepted") is True
            and adaptive
        ):
            current = base_catalog["current"]
            frozen = adaptive[0]
            if (frozen.parameters, frozen.policy) == (current.parameters, current.policy):
                catalog_by_symbol[symbol] = {"current": current}
            else:
                catalog_by_symbol[symbol] = {
                    "current": current,
                    frozen.name: frozen,
                }
            continue

        # Generation 0 already exhausted the static catalogue. Later generations
        # must not burn compute repeating the same grid: they compare only current
        # versus the newly generated training-led neighbourhood.
        current = base_catalog["current"]
        catalog = {"current": current}
        identities = {(current.parameters, current.policy)}
        for candidate in adaptive:
            identity = (candidate.parameters, candidate.policy)
            if identity in identities:
                continue
            catalog[candidate.name] = candidate
            identities.add(identity)
        catalog_by_symbol[symbol] = catalog
    catalog_digest = hashlib.sha256(
        json.dumps(
            {
                symbol: {name: _payload(candidate) for name, candidate in catalog.items()}
                for symbol, catalog in catalog_by_symbol.items()
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    research_version = f"HIXTON-V6-COIN-OPT-{catalog_digest[:12]}"

    current_profiles = {
        symbol: Candidate(
            "current",
            definition.parameters_for(symbol),
            definition.policy_for(symbol),
        )
        for symbol in definition.symbols
    }

    runner_profile_trace: dict[str, dict[str, dict[str, str]]] = {
        "10x250": {},
        "portfolio": {},
    }
    portfolio_plan = capital_plan(DEFAULT_MAX_CAPITAL_USDC)

    def run_batch(
        profiles: dict[str, Candidate],
        costs: CostModel,
        *,
        trace_label: str | None = None,
    ) -> Any:
        parameters_by_symbol = {
            symbol: candidate.parameters for symbol, candidate in profiles.items()
        }
        policies_by_symbol = {
            symbol: candidate.policy for symbol, candidate in profiles.items()
        }
        if trace_label is not None:
            runner_profile_trace["10x250"][trace_label] = _runner_profile_hashes(
                parameters_by_symbol,
                policies_by_symbol,
            )
        return run_isolated_batch(
            candles_by_symbol=candles,
            report_start_utc=report_start,
            report_end_utc=report_end,
            costs=costs,
            execution_rules=rules,
            strategy_parameters=definition.parameters,
            strategy_parameters_by_symbol=parameters_by_symbol,
            trade_policies_by_symbol=policies_by_symbol,
            strategy_semantics=definition.semantics,
            strategy_version=research_version,
            symbols=definition.symbols,
        )

    def run_portfolio(
        profiles: dict[str, Candidate],
        costs: CostModel,
        *,
        trace_label: str | None = None,
    ) -> Any:
        parameters_by_symbol = {
            symbol: candidate.parameters for symbol, candidate in profiles.items()
        }
        policies_by_symbol = {
            symbol: candidate.policy for symbol, candidate in profiles.items()
        }
        if trace_label is not None:
            runner_profile_trace["portfolio"][trace_label] = _runner_profile_hashes(
                parameters_by_symbol,
                policies_by_symbol,
            )
        return run_shared_portfolio_backtest(
            candles_by_symbol=candles,
            report_start_utc=report_start,
            report_end_utc=report_end,
            starting_cash=portfolio_plan.max_capital_usdc,
            target_notional=portfolio_plan.target_notional_usdc,
            slot_count=portfolio_plan.slot_count,
            costs=costs,
            execution_rules=rules,
            strategy_parameters=definition.parameters,
            strategy_parameters_by_symbol=parameters_by_symbol,
            trade_policies_by_symbol=policies_by_symbol,
            strategy_semantics=definition.semantics,
            strategy_version=research_version,
            slot_allocation=portfolio_plan.allocation_policy,
            apply_risk_limits=True,
            symbols=definition.symbols,
        )

    current_portfolio_baseline_raw = run_portfolio(
        current_profiles,
        BASELINE_COSTS,
        trace_label="current",
    )
    current_portfolio_stress_raw = run_portfolio(current_profiles, STRESS_COSTS)
    current_portfolio_baseline = _portfolio_summary(current_portfolio_baseline_raw)
    current_portfolio_stress = _portfolio_summary(current_portfolio_stress_raw)
    current_portfolio_baseline_equity = current_portfolio_baseline_raw.metrics.ending_equity
    current_portfolio_stress_equity = current_portfolio_stress_raw.metrics.ending_equity

    per_coin: dict[str, dict[str, object]] = {}
    robust_by_symbol: dict[str, list[tuple[str, Candidate]]] = {}
    result_lookup: dict[str, dict[str, dict[str, BacktestResult]]] = {}

    for symbol in definition.symbols:
        catalog = catalog_by_symbol[symbol]
        training: dict[str, dict[str, object]] = {}
        scores: dict[str, tuple[Decimal, Decimal, Decimal]] = {}
        behavior_keys: dict[str, tuple[object, ...]] = {}
        for name, candidate in catalog.items():
            train_results = []
            for window_name in ("train_a", "train_b"):
                low, high = windows[window_name]
                result = _run_single(
                    symbol=symbol,
                    candles=candles[symbol],
                    rules=rules[symbol],
                    start=low,
                    end=high,
                    candidate=candidate,
                    costs=STRESS_COSTS,
                    version=research_version,
                )
                train_results.append(result)
            scores[name] = (
                train_results[0].metrics.return_pct,
                train_results[1].metrics.return_pct,
                max(
                    train_results[0].metrics.max_drawdown_pct,
                    train_results[1].metrics.max_drawdown_pct,
                ),
            )
            behavior_keys[name] = tuple(
                _training_behavior_key(result) for result in train_results
            )
            training[name] = {
                "train_a_stress": _result_summary(train_results[0]),
                "train_b_stress": _result_summary(train_results[1]),
            }

        ordered = rank_training_candidates(scores, limit=len(scores))
        shortlist_names, behavior_duplicates_skipped = (
            freeze_distinct_training_shortlist(
                ordered,
                behavior_keys,
                limit=8,
            )
        )
        current = catalog["current"]
        low, high = windows["validation"]
        current_validation_base = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=low,
            end=high,
            candidate=current,
            costs=BASELINE_COSTS,
            version=research_version,
        )
        current_validation_stress = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=low,
            end=high,
            candidate=current,
            costs=STRESS_COSTS,
            version=research_version,
        )
        full_current = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=report_start,
            end=report_end,
            candidate=current,
            costs=BASELINE_COSTS,
            version=research_version,
        )
        full_current_stress = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=report_start,
            end=report_end,
            candidate=current,
            costs=STRESS_COSTS,
            version=research_version,
        )

        finalists: dict[str, object] = {}
        robust: list[tuple[str, Candidate]] = []
        result_lookup[symbol] = {}
        for name in shortlist_names:
            candidate = catalog[name]
            validation_base = _run_single(
                symbol=symbol,
                candles=candles[symbol],
                rules=rules[symbol],
                start=low,
                end=high,
                candidate=candidate,
                costs=BASELINE_COSTS,
                version=research_version,
            )
            validation_stress = _run_single(
                symbol=symbol,
                candles=candles[symbol],
                rules=rules[symbol],
                start=low,
                end=high,
                candidate=candidate,
                costs=STRESS_COSTS,
                version=research_version,
            )
            full_base = _run_single(
                symbol=symbol,
                candles=candles[symbol],
                rules=rules[symbol],
                start=report_start,
                end=report_end,
                candidate=candidate,
                costs=BASELINE_COSTS,
                version=research_version,
            )
            full_stress = _run_single(
                symbol=symbol,
                candles=candles[symbol],
                rules=rules[symbol],
                start=report_start,
                end=report_end,
                candidate=candidate,
                costs=STRESS_COSTS,
                version=research_version,
            )
            coin_gate = _passes_coin_gate(
                current_base=current_validation_base,
                current_stress=current_validation_stress,
                challenger_base=validation_base,
                challenger_stress=validation_stress,
                full_current=full_current,
                full_current_stress=full_current_stress,
                full_challenger=full_base,
                full_challenger_stress=full_stress,
            )
            result_lookup[symbol][name] = {
                "validation_baseline": validation_base,
                "validation_stress": validation_stress,
                "full_baseline": full_base,
                "full_stress": full_stress,
            }
            finalists[name] = {
                "profile": _payload(candidate),
                "validation_baseline": _result_summary(validation_base),
                "validation_stress": _result_summary(validation_stress),
                "full_baseline": _result_summary(full_base),
                "full_stress": _result_summary(full_stress),
                "coin_gate_passed": coin_gate,
            }
            if coin_gate:
                robust.append((name, candidate))

        robust_by_symbol[symbol] = robust
        per_coin[symbol] = {
            "current_profile": _payload(current),
            "training_candidates": training,
            "training_ranked": list(ordered),
            "training_behavior_duplicates_skipped": list(behavior_duplicates_skipped),
            "training_top_k_challengers": list(shortlist_names),
            "validation_current_baseline": _result_summary(current_validation_base),
            "validation_current_stress": _result_summary(current_validation_stress),
            "full_current_baseline": _result_summary(full_current),
            "full_current_stress": _result_summary(full_current_stress),
            "finalists": finalists,
            "robust_finalists": [name for name, _candidate in robust],
            "mission_frozen_promoted": symbol in MISSION_FROZEN_PROMOTED_SYMBOLS,
            "accepted": False,
            "accepted_profile": _payload(current),
            "full_accepted_baseline": _result_summary(full_current),
        }
        per_coin[symbol]["loss_cluster_analysis"] = _loss_signal_clusters(full_current)
        robust_names = ",".join(name for name, _candidate in robust) or "none"
        print(
            f"{symbol}: top8={','.join(shortlist_names)}; robust={robust_names}",
            flush=True,
        )

    marginal: dict[str, dict[str, object]] = {}
    portfolio_winner_by_symbol: dict[str, tuple[str, Candidate, Decimal, Decimal]] = {}
    for symbol in definition.symbols:
        symbol_trials: dict[str, object] = {}
        compatible: list[tuple[str, Candidate, Decimal, Decimal]] = []
        for name, candidate in robust_by_symbol[symbol]:
            trial_profiles = dict(current_profiles)
            trial_profiles[symbol] = candidate
            baseline_raw = run_portfolio(trial_profiles, BASELINE_COSTS)
            stress_raw = run_portfolio(trial_profiles, STRESS_COSTS)
            baseline_delta = baseline_raw.metrics.ending_equity - current_portfolio_baseline_equity
            stress_delta = stress_raw.metrics.ending_equity - current_portfolio_stress_equity
            portfolio_compatible = (
                baseline_delta >= D("0")
                and stress_delta >= D("0")
                and (baseline_delta > D("0") or stress_delta > D("0"))
            )
            symbol_trials[name] = {
                "profile": _payload(candidate),
                "baseline": _portfolio_summary(baseline_raw),
                "stress": _portfolio_summary(stress_raw),
                "baseline_delta_usdc": str(baseline_delta),
                "stress_delta_usdc": str(stress_delta),
                "portfolio_compatible": portfolio_compatible,
            }
            if portfolio_compatible:
                compatible.append((name, candidate, baseline_delta, stress_delta))
        if compatible:
            winner = max(
                compatible,
                key=lambda item: (
                    min(item[2], item[3]),
                    item[2],
                    item[3],
                    item[0],
                ),
            )
            portfolio_winner_by_symbol[symbol] = winner
            selected_name = winner[0]
        else:
            selected_name = "current"
        marginal[symbol] = {
            "trials": symbol_trials,
            "selected_for_combination": selected_name,
        }
        per_coin[symbol]["marginal_portfolio"] = marginal[symbol]

    winner_order = sorted(
        portfolio_winner_by_symbol,
        key=lambda symbol: (
            portfolio_winner_by_symbol[symbol][2],
            portfolio_winner_by_symbol[symbol][3],
            symbol,
        ),
        reverse=True,
    )
    assembled = dict(current_profiles)
    combined_baseline_raw = current_portfolio_baseline_raw
    combined_stress_raw = current_portfolio_stress_raw
    combination_steps: list[dict[str, object]] = []
    for symbol in winner_order:
        name, candidate, marginal_baseline_delta, marginal_stress_delta = (
            portfolio_winner_by_symbol[symbol]
        )
        trial_profiles = dict(assembled)
        trial_profiles[symbol] = candidate
        trial_baseline_raw = run_portfolio(trial_profiles, BASELINE_COSTS)
        trial_stress_raw = run_portfolio(trial_profiles, STRESS_COSTS)
        baseline_delta_from_combo = (
            trial_baseline_raw.metrics.ending_equity - combined_baseline_raw.metrics.ending_equity
        )
        stress_delta_from_combo = (
            trial_stress_raw.metrics.ending_equity - combined_stress_raw.metrics.ending_equity
        )
        accepted_step = (
            baseline_delta_from_combo >= D("0")
            and stress_delta_from_combo >= D("0")
            and (baseline_delta_from_combo > D("0") or stress_delta_from_combo > D("0"))
        )
        combination_steps.append(
            {
                "symbol": symbol,
                "candidate": name,
                "marginal_baseline_delta_usdc": str(marginal_baseline_delta),
                "marginal_stress_delta_usdc": str(marginal_stress_delta),
                "combination_baseline_delta_usdc": str(baseline_delta_from_combo),
                "combination_stress_delta_usdc": str(stress_delta_from_combo),
                "accepted_step": accepted_step,
                "trial_baseline": _portfolio_summary(trial_baseline_raw),
                "trial_stress": _portfolio_summary(trial_stress_raw),
            }
        )
        if accepted_step:
            assembled = trial_profiles
            combined_baseline_raw = trial_baseline_raw
            combined_stress_raw = trial_stress_raw

    for symbol in definition.symbols:
        accepted_candidate = assembled[symbol]
        accepted = accepted_candidate != current_profiles[symbol]
        per_coin[symbol]["accepted"] = accepted
        per_coin[symbol]["accepted_profile"] = _payload(accepted_candidate)
        if accepted:
            accepted_name = next(
                name
                for name, candidate in robust_by_symbol[symbol]
                if candidate == accepted_candidate
            )
            per_coin[symbol]["accepted_candidate_name"] = accepted_name
            per_coin[symbol]["full_accepted_baseline"] = _result_summary(
                result_lookup[symbol][accepted_name]["full_baseline"]
            )
        else:
            per_coin[symbol]["accepted_candidate_name"] = "current"

    current_hashes = _profile_hashes(current_profiles)
    candidate_hashes = _profile_hashes(assembled)

    current_batch_baseline = run_batch(
        current_profiles,
        BASELINE_COSTS,
        trace_label="current",
    )
    candidate_batch_baseline = run_batch(
        assembled,
        BASELINE_COSTS,
        trace_label="candidate",
    )
    candidate_portfolio_baseline_raw = run_portfolio(
        assembled,
        BASELINE_COSTS,
        trace_label="candidate",
    )
    if (
        candidate_portfolio_baseline_raw.metrics.ending_equity
        != combined_baseline_raw.metrics.ending_equity
    ):
        raise RuntimeError("candidate portfolio rerun is not deterministic")

    batches = {
        "current_baseline": _batch_summary(current_batch_baseline),
        "candidate_baseline": _batch_summary(candidate_batch_baseline),
        "current_stress": _batch_summary(run_batch(current_profiles, STRESS_COSTS)),
        "candidate_stress": _batch_summary(run_batch(assembled, STRESS_COSTS)),
    }
    portfolios = {
        "current_baseline": current_portfolio_baseline,
        "candidate_baseline": _portfolio_summary(candidate_portfolio_baseline_raw),
        "current_stress": current_portfolio_stress,
        "candidate_stress": _portfolio_summary(combined_stress_raw),
    }

    current_batch_hashes = runner_profile_trace["10x250"]["current"]
    current_portfolio_hashes = runner_profile_trace["portfolio"]["current"]
    candidate_batch_hashes = runner_profile_trace["10x250"]["candidate"]
    candidate_portfolio_hashes = runner_profile_trace["portfolio"]["candidate"]
    parity = {
        "declared_current_profile_hash_by_symbol": current_hashes,
        "declared_candidate_profile_hash_by_symbol": candidate_hashes,
        "current_10x250_profile_hash_by_symbol": current_batch_hashes,
        "current_portfolio_profile_hash_by_symbol": current_portfolio_hashes,
        "candidate_10x250_profile_hash_by_symbol": candidate_batch_hashes,
        "candidate_portfolio_profile_hash_by_symbol": candidate_portfolio_hashes,
        "current_match": (
            current_batch_hashes == current_portfolio_hashes == current_hashes
        ),
        "candidate_match": (
            candidate_batch_hashes == candidate_portfolio_hashes == candidate_hashes
        ),
    }
    if not parity["current_match"] or not parity["candidate_match"]:
        raise RuntimeError("profile hashes diverged between 10x250 and canonical portfolio")

    promotion_gate = aggregate_promotion_gate(batches, portfolios)

    evidence: dict[str, object] = {
        "schema_version": 3,
        "study": "coin-by-coin-v6-topk-marginal-optimization",
        "research_only": True,
        "search_generation": generation,
        "adaptive_source_used": previous_evidence is not None,
        "candidate_count_by_symbol": {
            symbol: len(catalog) for symbol, catalog in catalog_by_symbol.items()
        },
        "activation_performed": False,
        "active_strategy_version": definition.version,
        "research_version": research_version,
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "windows": {
            name: [low.isoformat(), high.isoformat()]
            for name, (low, high) in windows.items()
        },
        "selection_rule": (
            "training stress only freezes the ordered Top-8 challengers per coin; "
            "validation/full-3y baseline+stress may reject finalists but cannot introduce "
            "an unranked replacement"
        ),
        "validation_gate": (
            "each frozen finalist must be >= current return under validation baseline/stress, "
            "improve at least one, add no more than 5pp validation drawdown, and remain "
            "non-regressive on full-3y baseline/stress"
        ),
        "marginal_portfolio_gate": (
            "every robust finalist is tested alone in the canonical max-budget portfolio; "
            "baseline and stress must both be >= incumbent before it may enter the "
            "combination stage"
        ),
        "combination_rule": (
            "portfolio-compatible per-coin winners are added greedily by marginal baseline/stress "
            "value; each addition must be non-regressive versus the already assembled "
            "canonical portfolio baseline and stress"
        ),
        "per_coin": per_coin,
        "marginal_portfolio": marginal,
        "portfolio_plan": {
            "max_capital_usdc": str(portfolio_plan.max_capital_usdc),
            "slot_count": portfolio_plan.slot_count,
            "target_notional_usdc": str(portfolio_plan.target_notional_usdc),
            "allocation_policy": portfolio_plan.allocation_policy,
            "allocator_version": portfolio_plan.version,
        },
        "combination_steps": combination_steps,
        "assembled_candidate_profile_hash_by_symbol": candidate_hashes,
        "profile_parity": parity,
        "isolated_10x250": batches,
        "portfolio_max_budget": portfolios,
        "aggregate_promotion_gate": promotion_gate,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    return evidence


def _iteration_summary(evidence: dict[str, object]) -> dict[str, object]:
    per_coin = evidence.get("per_coin")
    if not isinstance(per_coin, dict):
        raise RuntimeError("adaptive optimization evidence is missing per_coin")
    accepted = sorted(
        symbol
        for symbol, raw in per_coin.items()
        if isinstance(raw, dict)
        and (
            raw.get("accepted") is True
            or raw.get("mission_frozen_promoted") is True
        )
    )
    unresolved: dict[str, str] = {}
    for symbol, raw in per_coin.items():
        if not isinstance(raw, dict):
            continue
        if (
            raw.get("accepted") is True
            or raw.get("mission_frozen_promoted") is True
        ):
            continue
        robust = raw.get("robust_finalists")
        unresolved[str(symbol)] = (
            "PORTFOLIO_OPPORTUNITY_COST"
            if isinstance(robust, list) and robust
            else "NO_ROBUST_HOLDOUT_FINALIST"
        )
    portfolios = evidence.get("portfolio_max_budget")
    candidate_equity = None
    candidate_stress_equity = None
    if isinstance(portfolios, dict):
        baseline = portfolios.get("candidate_baseline")
        stress = portfolios.get("candidate_stress")
        if isinstance(baseline, dict):
            candidate_equity = baseline.get("ending_equity")
        if isinstance(stress, dict):
            candidate_stress_equity = stress.get("ending_equity")
    return {
        "generation": evidence.get("search_generation"),
        "accepted_symbols": accepted,
        "unresolved": unresolved,
        "candidate_count_by_symbol": evidence.get("candidate_count_by_symbol"),
        "portfolio_candidate_ending_equity": candidate_equity,
        "portfolio_candidate_stress_ending_equity": candidate_stress_equity,
    }


def run_adaptive_cycle(
    output: Path,
    *,
    max_generations: int = MAX_ADAPTIVE_GENERATIONS,
) -> dict[str, object]:
    """Run bounded training-led generations until all coins improve or blockers remain."""

    if max_generations <= 0:
        raise ValueError("max_generations must be positive")

    previous: dict[str, object] | None = None
    history: list[dict[str, object]] = []
    final: dict[str, object] | None = None
    stop_reason = "MAX_GENERATIONS_REACHED"

    for generation in range(max_generations):
        generation_output = output.with_name(
            f"{output.stem}-g{generation}{output.suffix}"
        )
        final = run_cycle(
            generation_output,
            previous_evidence=previous,
            generation=generation,
        )
        summary = _iteration_summary(final)
        history.append(summary)
        unresolved = summary["unresolved"]
        if isinstance(unresolved, dict) and not unresolved:
            stop_reason = "ALL_TEN_ROBUST_PORTFOLIO_IMPROVEMENTS"
            break
        previous = final

    if final is None:
        raise RuntimeError("adaptive optimization produced no evidence")

    final["study"] = "coin-by-coin-v6-adaptive-topk-marginal-optimization"
    final["adaptive_search"] = {
        "max_generations": max_generations,
        "generations_completed": len(history),
        "stop_reason": stop_reason,
        "history": history,
        "final": history[-1],
        "selection_integrity": (
            "generation N+1 is created only from generation N training Top-K profiles; "
            "validation/full-window/portfolio evidence can reject or freeze a winner but "
            "never selects a new search direction"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(final, indent=2, default=str) + "\n", encoding="utf-8")
    return final


def main() -> None:
    output = Path("evidence") / "coin-optimization-cycle.json"
    evidence = run_adaptive_cycle(output)
    print(json.dumps(evidence, indent=2, default=str))


if __name__ == "__main__":
    main()

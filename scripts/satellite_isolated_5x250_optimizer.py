"""Adaptive isolated 5x250 Satellite optimizer.

This mirrors the established Core coin-by-coin optimization method at the
research-capital level: each Satellite is optimized independently with 250 USDC
over the same canonical three-year window as the protected f649 Core evidence.

Important:
- 5x250 / 15x250 are optimization-lab views, not shared live capital.
- Selection/evolution uses TRAINING windows only.
- Direct-USDC validation and full-window checks may reject/freeze, never choose
  a new search direction.
- The protected ten-Core product is not mutated.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import StrategyParameters
from hixton.domain.versions import V1_STRATEGY
from scripts.satellite_v1_evolution_research import (
    SATELLITES,
    REFERENCE_CAPITAL,
    _adapt,
    _metrics,
    _rules,
    _run,
    _candidate_grid,
)

D = Decimal
BAR = timedelta(hours=1)
MISSION = Path("agent_memory/autonomy/current_mission.json")
SOURCES = Path("agent_memory/autonomy/satellite_v1_idle_horizon_sources.json")
OUTPUT = Path("evidence/satellite-isolated-5x250-optimizer.json")
MAX_GENERATIONS = 3
TOP_ANCHORS = 2
CORE_ISOLATED_10X250_ENDING = D("8107.07268728784085000000")
CORE_ISOLATED_10X250_STARTING = D("2500")
CORE_ISOLATED_10X250_STRESS_ENDING = D("7597.1773394368352000000")


def _canonical_window() -> tuple[datetime, datetime]:
    mission = json.loads(MISSION.read_text(encoding="utf-8"))
    baseline = mission.get("canonical_core_baseline") or {}
    start_raw = baseline.get("report_start_utc")
    end_raw = baseline.get("report_end_utc")
    if not start_raw or not end_raw:
        raise RuntimeError("canonical Core baseline window missing from current_mission.json")
    start = datetime.fromisoformat(str(start_raw)).astimezone(timezone.utc)
    end = datetime.fromisoformat(str(end_raw)).astimezone(timezone.utc)
    if end <= start:
        raise RuntimeError("invalid canonical Core baseline window")
    return start, end


def _param_id(p: StrategyParameters) -> tuple[object, ...]:
    return (
        p.vidya_length,
        p.momentum_length,
        p.smoothing_length,
        p.atr_length,
        round(p.band_multiplier, 4),
        p.warmup_bars,
    )


def _local_candidates(anchor: StrategyParameters, generation: int, prefix: str) -> list[tuple[str, StrategyParameters, str]]:
    radius = generation + 1
    out: list[tuple[str, StrategyParameters, str]] = []
    seen: set[tuple[object, ...]] = set()

    def add(name: str, p: StrategyParameters, family: str) -> None:
        key = _param_id(p)
        if key in seen:
            return
        seen.add(key)
        out.append((name, p, family))

    add(f"{prefix}_anchor", anchor, "adaptive_anchor")
    vidya_step = radius
    mom_step = 2 * radius
    smooth_step = 2 * radius
    atr_step = 15 * radius
    band_step = 0.10 * radius

    for sign, tag in ((-1, "m"), (1, "p")):
        add(
            f"{prefix}_vidya_{tag}{vidya_step}",
            replace(anchor, vidya_length=max(2, anchor.vidya_length + sign * vidya_step)),
            "adaptive_vidya",
        )
        add(
            f"{prefix}_mom_{tag}{mom_step}",
            replace(anchor, momentum_length=max(4, anchor.momentum_length + sign * mom_step)),
            "adaptive_momentum",
        )
        add(
            f"{prefix}_smooth_{tag}{smooth_step}",
            replace(anchor, smoothing_length=max(2, anchor.smoothing_length + sign * smooth_step)),
            "adaptive_smoothing",
        )
        add(
            f"{prefix}_atr_{tag}{atr_step}",
            replace(anchor, atr_length=max(15, min(300, anchor.atr_length + sign * atr_step))),
            "adaptive_atr",
        )
        add(
            f"{prefix}_band_{tag}{int(band_step*100):02d}",
            replace(anchor, band_multiplier=max(0.5, round(anchor.band_multiplier + sign * band_step, 2))),
            "adaptive_band",
        )
        add(
            f"{prefix}_mom_smooth_{tag}",
            replace(
                anchor,
                momentum_length=max(4, anchor.momentum_length + sign * mom_step),
                smoothing_length=max(2, anchor.smoothing_length + sign * smooth_step),
            ),
            "adaptive_combo",
        )
        add(
            f"{prefix}_vidya_band_{tag}",
            replace(
                anchor,
                vidya_length=max(2, anchor.vidya_length + sign * vidya_step),
                band_multiplier=max(0.5, round(anchor.band_multiplier + sign * band_step, 2)),
            ),
            "adaptive_combo",
        )
        add(
            f"{prefix}_atr_band_{tag}",
            replace(
                anchor,
                atr_length=max(15, min(300, anchor.atr_length + sign * atr_step)),
                band_multiplier=max(0.5, round(anchor.band_multiplier + sign * band_step, 2)),
            ),
            "adaptive_combo",
        )
    return out


def _score(train_a: Any, train_b: Any) -> tuple[D, D, D, int]:
    # Same philosophy as the established Core optimizer: both independent
    # training years must matter; worst-window return dominates.
    ra = D(str(train_a.metrics.return_pct))
    rb = D(str(train_b.metrics.return_pct))
    worst_dd = max(
        D(str(train_a.metrics.max_drawdown_pct)),
        D(str(train_b.metrics.max_drawdown_pct)),
    )
    trades = min(train_a.metrics.completed_trades, train_b.metrics.completed_trades)
    return (min(ra, rb), ra + rb, -worst_dd, trades)


def _passes_gate(validation_base: Any, validation_stress: Any, full_base: Any, full_stress: Any) -> bool:
    return (
        validation_base.metrics.net_pnl > 0
        and validation_stress.metrics.net_pnl > 0
        and full_base.metrics.net_pnl > 0
        and full_stress.metrics.net_pnl > 0
        and validation_stress.metrics.completed_trades > 0
        and full_stress.metrics.completed_trades > 0
    )


def main() -> None:
    start, end = _canonical_window()
    train_a_end = start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    if train_b_end >= end:
        raise RuntimeError("canonical 3y window too short for 2y training + validation")
    validation_start = train_b_end

    source_checkpoint = json.loads(SOURCES.read_text(encoding="utf-8"))
    source_rows = source_checkpoint.get("per_symbol")
    if not isinstance(source_rows, dict):
        raise RuntimeError("Satellite source checkpoint missing per_symbol")
    if tuple(source_rows) != SATELLITES:
        raise RuntimeError(f"Satellite set drifted: {tuple(source_rows)!r}")

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol: dict[str, object] = {}
    accepted_symbols: list[str] = []
    accepted_full_baseline_ending = D("0")
    accepted_full_stress_ending = D("0")

    for symbol in SATELLITES:
        rules = _rules(client, symbol)
        proxy_symbol = str(source_rows[symbol]["history_source_for_training"])
        warmup = V1_STRATEGY.parameters.warmup_bars

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

        # Generation 0 uses the established V1-derived bounded grid plus the
        # previous training champion as an additional anchor.
        base_grid = list(_candidate_grid())
        prior_raw = source_rows[symbol].get("parameters")
        if isinstance(prior_raw, dict):
            prior = StrategyParameters(**prior_raw)
            base_grid.append(("PRIOR_TRAINING_CHAMPION", prior, "prior_training_anchor"))

        generation_history: list[dict[str, object]] = []
        catalog = base_grid
        frozen: dict[str, object] | None = None

        for generation in range(MAX_GENERATIONS):
            rows: list[dict[str, object]] = []
            ranked: list[tuple[tuple[D, D, D, int], str, StrategyParameters, str, dict[str, object]]] = []
            seen: set[tuple[object, ...]] = set()

            for name, params, family in catalog:
                ident = _param_id(params)
                if ident in seen:
                    continue
                seen.add(ident)
                version = f"HIXTON-SAT-5X250-G{generation}-{symbol}-{name}"
                ta = _run(
                    symbol=symbol, candles=proxy, rules=rules,
                    start=start, end=train_a_end, costs=STRESS_COSTS,
                    params=params, version=version,
                )
                tb = _run(
                    symbol=symbol, candles=proxy, rules=rules,
                    start=train_a_end, end=train_b_end, costs=STRESS_COSTS,
                    params=params, version=version,
                )
                payload = {
                    "name": name,
                    "family": family,
                    "parameters": asdict(params),
                    "train_a_stress": _metrics(ta),
                    "train_b_stress": _metrics(tb),
                }
                rows.append(payload)
                ranked.append((_score(ta, tb), name, params, family, payload))

            ranked.sort(key=lambda item: item[0], reverse=True)
            if not ranked:
                raise RuntimeError(f"{symbol}: empty candidate ranking")
            champion_score, champion_name, champion_params, champion_family, champion_training = ranked[0]

            # Validation/full reporting is applied only to the training-selected champion.
            version = f"HIXTON-SAT-5X250-FROZEN-G{generation}-{symbol}"
            v_base = _run(
                symbol=symbol, candles=direct, rules=rules,
                start=validation_start, end=end, costs=BASELINE_COSTS,
                params=champion_params, version=version,
            )
            v_stress = _run(
                symbol=symbol, candles=direct, rules=rules,
                start=validation_start, end=end, costs=STRESS_COSTS,
                params=champion_params, version=version,
            )
            full_base = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=start, end=end, costs=BASELINE_COSTS,
                params=champion_params, version=version,
            )
            full_stress = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=start, end=end, costs=STRESS_COSTS,
                params=champion_params, version=version,
            )
            passed = _passes_gate(v_base, v_stress, full_base, full_stress)

            generation_history.append({
                "generation": generation,
                "candidate_count": len(rows),
                "training_champion": champion_training,
                "training_score": [str(x) for x in champion_score],
                "validation_baseline": _metrics(v_base),
                "validation_stress": _metrics(v_stress),
                "full_3y_proxy_baseline": _metrics(full_base),
                "full_3y_proxy_stress": _metrics(full_stress),
                "gate_passed": passed,
                "top_training": [item[4] for item in ranked[:5]],
            })

            if passed:
                frozen = {
                    "generation": generation,
                    "name": champion_name,
                    "family": champion_family,
                    "parameters": asdict(champion_params),
                    "validation_baseline": _metrics(v_base),
                    "validation_stress": _metrics(v_stress),
                    "full_3y_proxy_baseline": _metrics(full_base),
                    "full_3y_proxy_stress": _metrics(full_stress),
                }
                break

            # Next generation is created ONLY from current generation TRAINING top anchors.
            next_catalog: list[tuple[str, StrategyParameters, str]] = []
            for anchor_index, item in enumerate(ranked[:TOP_ANCHORS]):
                _, anchor_name, anchor_params, _, _ = item
                next_catalog.extend(
                    _local_candidates(
                        anchor_params,
                        generation=generation + 1,
                        prefix=f"G{generation+1}_A{anchor_index}_{anchor_name}",
                    )
                )
            catalog = next_catalog

        if frozen is not None:
            accepted_symbols.append(symbol)
            accepted_full_baseline_ending += D(str(frozen["full_3y_proxy_baseline"]["ending_equity"]))
            accepted_full_stress_ending += D(str(frozen["full_3y_proxy_stress"]["ending_equity"]))

        per_symbol[symbol] = {
            "proxy_symbol": proxy_symbol,
            "starting_capital_usdc": str(REFERENCE_CAPITAL),
            "generation_history": generation_history,
            "accepted_profile": frozen,
            "accepted": frozen is not None,
            "rejection_reason": None if frozen is not None else "NO_ROBUST_ISOLATED_250_PROFILE_AFTER_3_ADAPTIVE_GENERATIONS",
        }

    accepted_count = len(accepted_symbols)
    partial_start = CORE_ISOLATED_10X250_STARTING + D(accepted_count) * REFERENCE_CAPITAL
    partial_baseline_end = CORE_ISOLATED_10X250_ENDING + accepted_full_baseline_ending
    partial_stress_end = CORE_ISOLATED_10X250_STRESS_ENDING + accepted_full_stress_ending

    result = {
        "schema_version": 1,
        "study": "SATELLITE_ISOLATED_5X250_ADAPTIVE_OPTIMIZER",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": source_checkpoint.get("protected_product_sha"),
        "canonical_window": {
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "training_a_end_utc": train_a_end.isoformat(),
            "training_b_end_utc": train_b_end.isoformat(),
            "validation_start_utc": validation_start.isoformat(),
        },
        "methodology": {
            "core_reference_view": "isolated_10x250",
            "satellite_extension_view": "isolated_5x250",
            "combined_research_view": "isolated_15x250",
            "each_market_starting_capital_usdc": "250",
            "isolated_15x250_is_live_capital": False,
            "adaptive_generations": MAX_GENERATIONS,
            "search_direction_uses_training_only": True,
            "direct_usdc_validation_rejection_only": True,
            "full_3y_proxy_reporting_not_selection": True,
        },
        "core_isolated_10x250_exact_head_reference": {
            "starting_equity_usdc": str(CORE_ISOLATED_10X250_STARTING),
            "baseline_ending_equity_usdc": str(CORE_ISOLATED_10X250_ENDING),
            "stress_ending_equity_usdc": str(CORE_ISOLATED_10X250_STRESS_ENDING),
        },
        "per_symbol": per_symbol,
        "accepted_satellites": accepted_symbols,
        "accepted_count": accepted_count,
        "validated_partial_isolated_extension": {
            "starting_equity_usdc": str(partial_start),
            "baseline_ending_equity_usdc": str(partial_baseline_end),
            "stress_ending_equity_usdc": str(partial_stress_end),
            "note": "Contains Core 10 plus only Satellites that passed isolated validation. This is optimization evidence, not shared-account/live performance.",
        },
        "next_stage": (
            "SATELLITE_SHARED_IDLE_INTEGRATION"
            if accepted_count > 0
            else "SATELLITE_ISOLATED_5X250_DIAGNOSIS"
        ),
        "safety": {
            "protected_core_mutated": False,
            "paper_or_live_activated": False,
            "orders_sent": False,
            "private_credentials_used": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "study": result["study"],
        "accepted_satellites": accepted_symbols,
        "accepted_count": accepted_count,
        "partial_isolated_extension": result["validated_partial_isolated_extension"],
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()

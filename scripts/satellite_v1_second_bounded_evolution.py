"""Second bounded V1 evolution for SUI/NEAR/AAVE/BCH.

The family for each market is frozen from Run-65 TRAINING topology only.
The direct-USDC year remains rejection-only and cannot choose or retune parameters.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import StrategyParameters
from hixton.domain.versions import V1_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.satellite_v1_evolution_research import (
    BAR,
    HOLDOUT,
    _adapt,
    _decimal,
    _metrics,
    _rank_training,
    _rules,
    _run,
)

SATELLITES = ("SUIUSDC", "NEARUSDC", "AAVEUSDC", "BCHUSDC")
CHECKPOINT = Path("agent_memory/autonomy/satellite_v1_candidates.json")
OUTPUT = Path("evidence/satellite-v1-second-bounded-evolution.json")

# Chosen strictly from the first-round TRAINING winner topology:
# ATR72 won for SUI/NEAR, momentum12 won at AAVE's tested lower edge,
# and band2.8 was BCH's only positive robust training survivor at the upper edge.
LOCAL_FAMILIES: dict[str, tuple[str, tuple[object, ...]]] = {
    "SUIUSDC": ("atr_length", (56, 64, 72, 80, 96)),
    "NEARUSDC": ("atr_length", (56, 64, 72, 80, 96)),
    "AAVEUSDC": ("momentum_length", (6, 8, 10, 12, 14)),
    "BCHUSDC": ("band_multiplier", (2.6, 2.8, 3.0, 3.2, 3.4)),
}


def _family(
    symbol: str,
    base: StrategyParameters,
) -> list[tuple[str, StrategyParameters]]:
    axis, values = LOCAL_FAMILIES[symbol]
    candidates: list[tuple[str, StrategyParameters]] = []
    for value in values:
        payload = asdict(base)
        payload[axis] = value
        candidates.append(
            (f"LOCAL_{axis}_{value}", StrategyParameters(**payload))
        )
    return candidates


def main() -> None:
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    sources = checkpoint.get("per_symbol")
    if not isinstance(sources, dict):
        raise RuntimeError("candidate checkpoint missing per_symbol")

    _, report_start, report_end = safe_closed_window()
    holdout_start = report_end - HOLDOUT
    training_end = holdout_start
    warmup = V1_STRATEGY.parameters.warmup_bars
    training_warmup_start = report_start - warmup * BAR
    holdout_warmup_start = holdout_start - warmup * BAR

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol: dict[str, object] = {}
    accepted: list[str] = []

    for symbol in SATELLITES:
        source = sources.get(symbol)
        if not isinstance(source, dict):
            raise RuntimeError(f"{symbol}: source checkpoint missing")
        if source.get("advance_to_shared_replay") is True:
            raise RuntimeError(f"{symbol}: already accepted in first evolution")

        source_params = source.get("parameters")
        proxy_symbol = source.get("history_source_for_training")
        if not isinstance(source_params, dict) or not isinstance(proxy_symbol, str):
            raise RuntimeError(f"{symbol}: malformed source checkpoint")
        base_params = StrategyParameters(**source_params)
        rules = _rules(client, symbol)

        proxy = _adapt(
            client.fetch_klines(
                proxy_symbol,
                start=training_warmup_start,
                end_exclusive=training_end,
            ),
            symbol,
        )
        audit_candles(
            proxy,
            expected_symbol=symbol,
            expected_start=training_warmup_start,
            expected_end_exclusive=training_end,
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

        training_rows: list[dict[str, object]] = []
        for name, params in _family(symbol, base_params):
            version = f"HIXTON-SAT-V1-ROUND2-{symbol}-{name}"
            baseline = _run(
                symbol=symbol,
                candles=proxy,
                rules=rules,
                start=report_start,
                end=training_end,
                costs=BASELINE_COSTS,
                params=params,
                version=version,
            )
            stress = _run(
                symbol=symbol,
                candles=proxy,
                rules=rules,
                start=report_start,
                end=training_end,
                costs=STRESS_COSTS,
                params=params,
                version=version,
            )
            training_rows.append(
                {
                    "name": name,
                    "parameters": asdict(params),
                    "baseline": _metrics(baseline),
                    "stress": _metrics(stress),
                }
            )

        ranked = _rank_training(training_rows)
        champion = ranked[0] if ranked else None
        if champion is None:
            per_symbol[symbol] = {
                "source_champion": source.get("champion_name"),
                "family_axis": LOCAL_FAMILIES[symbol][0],
                "family_values": list(LOCAL_FAMILIES[symbol][1]),
                "training_champion": None,
                "holdout": None,
                "advance_to_shared_replay": False,
                "rejection_reason": "NO_POSITIVE_ROBUST_LOCAL_TRAINING_CANDIDATE",
            }
            continue

        params = StrategyParameters(**champion["parameters"])
        version = f"HIXTON-SAT-V1-ROUND2-CANDIDATE-{symbol}"
        holdout_baseline = _metrics(
            _run(
                symbol=symbol,
                candles=direct,
                rules=rules,
                start=holdout_start,
                end=report_end,
                costs=BASELINE_COSTS,
                params=params,
                version=version,
            )
        )
        holdout_stress = _metrics(
            _run(
                symbol=symbol,
                candles=direct,
                rules=rules,
                start=holdout_start,
                end=report_end,
                costs=STRESS_COSTS,
                params=params,
                version=version,
            )
        )
        holdout = {"baseline": holdout_baseline, "stress": holdout_stress}
        holdout_pass = (
            _decimal(holdout_baseline, "net_pnl") > 0
            and _decimal(holdout_stress, "net_pnl") > 0
            and int(holdout_stress["completed_trades"]) > 0
            and holdout_stress["profit_per_position_hour"] is not None
        )
        if holdout_pass:
            accepted.append(symbol)

        per_symbol[symbol] = {
            "source_champion": source.get("champion_name"),
            "family_axis": LOCAL_FAMILIES[symbol][0],
            "family_values": list(LOCAL_FAMILIES[symbol][1]),
            "training_champion": champion,
            "top_training_candidates": ranked[:5],
            "holdout": holdout,
            "advance_to_shared_replay": holdout_pass,
            "rejection_reason": (
                None if holdout_pass else "DIRECT_USDC_HOLDOUT_REJECTION"
            ),
        }

    evidence = {
        "schema_version": 1,
        "study": "SATELLITE_V1_SECOND_BOUNDED_EVOLUTION",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "source_first_evolution_run_id": checkpoint.get("source_run_id"),
        "starting_strategy": (
            "per-market Run-65 training champion with original DMS_V1 semantics"
        ),
        "family_selection_basis": (
            "Frozen from Run-65 training topology only. Direct-USDC holdout "
            "outcomes are not read to choose the axis or local values."
        ),
        "family_by_symbol": {
            symbol: {"axis": axis, "values": list(values)}
            for symbol, (axis, values) in LOCAL_FAMILIES.items()
        },
        "selection_contract": {
            "training_proxy_may_rank": True,
            "direct_usdc_holdout_may_rank": False,
            "direct_usdc_holdout_rejection_only": True,
            "future_shifted_red_team_not_used_for_selection": True,
        },
        "per_symbol": per_symbol,
        "accepted_for_shared_core_idle_replay": accepted,
        "next_stage": (
            "SATELLITE_V1_SHARED_CORE_IDLE_REPLAY_ROUND2"
            if accepted
            else "SATELLITE_V1_REJECT_REMAINING_OR_THIRD_CAUSAL_FAMILY"
        ),
        "safety": {
            "core_v6_profiles_used_as_satellite_seed": False,
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "future_outcomes_used_for_selection": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "study": evidence["study"],
                "accepted_for_shared_core_idle_replay": accepted,
                "next_stage": evidence["next_stage"],
                "training_champions": {
                    symbol: (
                        None
                        if row["training_champion"] is None
                        else row["training_champion"]["name"]
                    )
                    for symbol, row in per_symbol.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

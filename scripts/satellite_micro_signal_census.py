"""Training-only signal excursion census for Satellite gap fillers.

This is a diagnostic bridge after Run #78/#79 rejected the bounded VIDYA
micro-filler parameter family. It does not promote or trade anything. The study
asks a different causal question: after a point-in-time V1 flip-up signal, how
often does a small executable upside target arrive before an equally sized
downside stop at 2/4/6/12h horizons?

Only the TRAINING proxy window is inspected. Direct-USDC holdout is deliberately
not read for selection or tuning. The next strategy family may use this census
to define a fixed small-target / bounded-stop exit family, which must then be
validated independently against the protected Core idle mask.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V1_STRATEGY
from scripts.satellite_shared_portfolio_research import _load_histories, _rules
from hixton.data.binance import BinancePublicClient

SOURCES = Path("agent_memory/autonomy/satellite_v1_idle_horizon_sources.json")
OUTPUT = Path("evidence/satellite-micro-signal-census.json")
HORIZONS = (2, 4, 6, 12)
TARGETS_PCT = (0.25, 0.50, 0.75, 1.00)


def _first_touch(entry: float, future: list[Any], pct: float) -> str:
    up = entry * (1.0 + pct / 100.0)
    down = entry * (1.0 - pct / 100.0)
    for candle in future:
        up_hit = candle.high >= up
        down_hit = candle.low <= down
        if up_hit and down_hit:
            return "AMBIGUOUS_SAME_BAR"
        if up_hit:
            return "UP_FIRST"
        if down_hit:
            return "DOWN_FIRST"
    return "NONE"


def _load_sources() -> dict[str, Any]:
    value = json.loads(SOURCES.read_text(encoding="utf-8"))
    rows = value.get("per_symbol")
    if not isinstance(rows, dict):
        raise RuntimeError("Satellite source checkpoint missing per_symbol")
    expected = ("SUIUSDC", "NEARUSDC", "UNIUSDC", "AAVEUSDC", "BCHUSDC")
    if tuple(rows) != expected:
        raise RuntimeError(f"primary Satellite set drifted: {tuple(rows)!r}")
    return value


def main() -> None:
    checkpoint = _load_sources()
    rows = checkpoint["per_symbol"]
    satellites = tuple(rows)
    client = BinancePublicClient(base_url="https://data-api.binance.vision")

    # Core symbols are included only because the shared history loader establishes the
    # exact canonical training/holdout boundaries and continuity provenance.
    from hixton.domain.versions import V6_COIN_STRATEGY

    all_symbols = V6_COIN_STRATEGY.symbols + satellites
    rules = _rules(client, all_symbols)
    (
        report_start,
        holdout_start,
        _report_end,
        proxy_candles,
        _validation_candles,
        provenance,
    ) = _load_histories(
        client=client,
        satellite_symbols=satellites,
        satellite_sources={
            symbol: str(rows[symbol]["history_source_for_training"])
            for symbol in satellites
        },
        execution_rules=rules,
    )

    per_symbol: dict[str, object] = {}
    aggregate_counts = {
        f"{h}h_{pct:.2f}": {"UP_FIRST": 0, "DOWN_FIRST": 0, "AMBIGUOUS_SAME_BAR": 0, "NONE": 0}
        for h in HORIZONS for pct in TARGETS_PCT
    }

    for symbol in satellites:
        candles = proxy_candles[symbol]
        points = evaluate_batch(
            symbol,
            candles,
            parameters=V1_STRATEGY.parameters,
            semantics=V1_STRATEGY.semantics,
            strategy_version="SATELLITE-V1-SIGNAL-CENSUS",
        )
        index_by_close = {c.close_time_utc: i for i, c in enumerate(candles)}
        signals = [
            p for p in points
            if p.tradable and p.flip_up and report_start <= p.candle.close_time_utc < holdout_start
        ]
        counts = {
            f"{h}h_{pct:.2f}": {"UP_FIRST": 0, "DOWN_FIRST": 0, "AMBIGUOUS_SAME_BAR": 0, "NONE": 0}
            for h in HORIZONS for pct in TARGETS_PCT
        }

        for point in signals:
            idx = index_by_close[point.candle.close_time_utc]
            if idx + 1 >= len(candles):
                continue
            entry = candles[idx + 1].open
            for h in HORIZONS:
                future = candles[idx + 1 : min(len(candles), idx + 1 + h)]
                for pct in TARGETS_PCT:
                    key = f"{h}h_{pct:.2f}"
                    outcome = _first_touch(entry, future, pct)
                    counts[key][outcome] += 1
                    aggregate_counts[key][outcome] += 1

        scored = []
        for key, values in counts.items():
            decisive = int(values["UP_FIRST"]) + int(values["DOWN_FIRST"])
            up_rate = (int(values["UP_FIRST"]) / decisive) if decisive else 0.0
            coverage = decisive / max(1, len(signals))
            scored.append({
                "key": key,
                "up_first_rate_decisive": up_rate,
                "decisive_coverage": coverage,
                "up_first": values["UP_FIRST"],
                "down_first": values["DOWN_FIRST"],
                "ambiguous_same_bar": values["AMBIGUOUS_SAME_BAR"],
                "none": values["NONE"],
            })
        scored.sort(
            key=lambda x: (
                x["up_first_rate_decisive"],
                x["decisive_coverage"],
                x["up_first"],
            ),
            reverse=True,
        )
        per_symbol[symbol] = {
            "training_flip_up_signals": len(signals),
            "first_touch_counts": counts,
            "top_training_small_target_patterns": scored[:5],
        }

    aggregate_scored = []
    total_signals = sum(int(v["training_flip_up_signals"]) for v in per_symbol.values())
    for key, values in aggregate_counts.items():
        decisive = int(values["UP_FIRST"]) + int(values["DOWN_FIRST"])
        aggregate_scored.append({
            "key": key,
            "up_first_rate_decisive": (int(values["UP_FIRST"]) / decisive) if decisive else 0.0,
            "decisive_coverage": decisive / max(1, total_signals),
            **values,
        })
    aggregate_scored.sort(
        key=lambda x: (
            x["up_first_rate_decisive"],
            x["decisive_coverage"],
            x["UP_FIRST"],
        ),
        reverse=True,
    )

    result = {
        "schema_version": 1,
        "study": "SATELLITE_MICRO_SIGNAL_CENSUS",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "training_window": {
            "start_utc": report_start.isoformat(),
            "end_exclusive_utc": holdout_start.isoformat(),
        },
        "signals": {
            "strategy": "UNCHANGED_V1_DMS_V1_FLIP_UP",
            "parameters": asdict(V1_STRATEGY.parameters),
            "entry_reference": "next_candle_open_after_signal_close",
        },
        "horizons_hours": list(HORIZONS),
        "symmetric_target_stop_pct": list(TARGETS_PCT),
        "per_symbol": per_symbol,
        "aggregate": {
            "training_flip_up_signals": total_signals,
            "first_touch_counts": aggregate_counts,
            "top_training_small_target_patterns": aggregate_scored[:8],
        },
        "selection_contract": {
            "training_only": True,
            "direct_usdc_holdout_read": False,
            "future_excursions_are_training_labels_only": True,
            "next_candidate_must_be_frozen_before_holdout": True,
        },
        "next_stage": "SATELLITE_MICRO_HARVEST_FIXED_EXIT_FAMILY",
        "next_family_contract": (
            "Use only TRAINING census to freeze one bounded take-profit/stop/horizon family; "
            "then run exact Core-idle one-shared-C baseline+stress and Direct-USDC rejection-only."
        ),
        "provenance_by_symbol": provenance,
        "safety": {
            "orders_sent": False,
            "paper_or_live_activated": False,
            "private_credentials_used": False,
            "protected_core_mutated": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "study": result["study"],
        "training_flip_up_signals": total_signals,
        "top_training_small_target_patterns": aggregate_scored[:8],
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()

"""Preserve owned one-shot exits across an explicit product strategy upgrade."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from hixton.domain.models import IndicatorPoint
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import (
    FROZEN_STRATEGY_DEFINITIONS,
    STRATEGY_DEFINITIONS,
    StrategyDefinition,
)


def continuation_strategy(database: Path, active: StrategyDefinition) -> StrategyDefinition:
    """Resolve a known frozen contract, never rewrite its identity or re-arm entry."""
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        if (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='signal_trial'"
            ).fetchone()
            is None
        ):
            return active
        row = connection.execute("SELECT * FROM signal_trial WHERE singleton=1").fetchone()
        if row is None or row["state"] in {"COMPLETED", "CANCELED", "FAILED"}:
            return active
        owned = row["state"] in {"OPEN", "EXIT_PENDING", "AWAITING_RECONCILIATION", "NEEDS_REVIEW"}
        if row["state"] == "ENTRY_PENDING" and row["buy_id"]:
            intent = connection.execute(
                "SELECT state FROM trial_intents WHERE intent_id=?", (row["buy_id"],)
            ).fetchone()
            owned = intent is not None and intent["state"] != "CREATED"
        if not owned:
            return active  # An unsubmitted stale entitlement must still be canceled.
        frozen = json.loads(row["strategy_json"])
        for definition in (active, *STRATEGY_DEFINITIONS.values(), *FROZEN_STRATEGY_DEFINITIONS):
            if definition.config_payload() == frozen:
                return definition
    raise RuntimeError("Owned trial uses an unknown frozen strategy; manual review required")


class FrozenTrialPoints:
    """Recompute changed profiles from the same closed candles, with no future data."""

    def __init__(self, active: StrategyDefinition, frozen: StrategyDefinition) -> None:
        self.active = active
        self.frozen = frozen
        self._inputs: dict[str, Sequence[IndicatorPoint]] = {}
        self._outputs: dict[str, tuple[IndicatorPoint, ...]] = {}

    def __call__(
        self, points: Mapping[str, Sequence[IndicatorPoint]]
    ) -> Mapping[str, Sequence[IndicatorPoint]]:
        if self.active.config_payload() == self.frozen.config_payload():
            return points
        result: dict[str, tuple[IndicatorPoint, ...]] = {}
        for symbol in self.frozen.symbols:
            series = points.get(symbol, ())
            if not series:
                return {}  # Incomplete data may not trigger a capacity handoff.
            if self._inputs.get(symbol) is series:
                result[symbol] = self._outputs[symbol]
                continue
            if any(
                p.strategy_version != self.active.version
                or not p.candle.closed
                or not p.candle.ohlc_is_valid
                for p in series
            ):
                raise ValueError("Frozen trial requires valid closed active-strategy candles")
            same_indicators = self.active.parameters_for(symbol) == self.frozen.parameters_for(
                symbol
            ) and self.active.semantics_for(symbol) == self.frozen.semantics_for(symbol)
            output = (
                tuple(replace(p, strategy_version=self.frozen.version) for p in series)
                if same_indicators
                else tuple(
                    evaluate_batch(
                        symbol,
                        (p.candle for p in series),
                        parameters=self.frozen.parameters_for(symbol),
                        semantics=self.frozen.semantics_for(symbol),
                        strategy_version=self.frozen.version,
                    )
                )
            )
            self._inputs[symbol] = series
            self._outputs[symbol] = output
            result[symbol] = output
        return result

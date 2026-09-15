"""Rebuild the canonical 1h indicator cache from validated local candles."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from hixton.constants import SYMBOLS, TIMEFRAME_DELTA
from hixton.data.quality import DataQualityReport, audit_candles
from hixton.data.storage import CandleStore
from hixton.domain.models import Candle, IndicatorPoint
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V1_STRATEGY, StrategyDefinition


def available_report_start(
    candles: dict[str, list[Candle]], requested_start: datetime, end: datetime
) -> datetime:
    """Common available window only; do not forgive internal or trailing gaps."""
    if not candles or any(not series for series in candles.values()):
        raise ValueError("Missing market history")
    starts = []
    for symbol, series in candles.items():
        audit_candles(
            series,
            expected_symbol=symbol,
            expected_start=series[0].open_time_utc,
            expected_end_exclusive=end,
        ).require_valid()
        starts.append(series[0].open_time_utc + 400 * TIMEFRAME_DELTA)
    actual = max(requested_start, max(starts))
    if actual >= end:
        raise ValueError("Insufficient common history after 400 warm-up bars")
    return actual


def rebuild_analysis(
    database_path: Path,
    *,
    start: datetime,
    end_exclusive: datetime,
    strategy: StrategyDefinition = V1_STRATEGY,
    starts_by_symbol: dict[str, datetime] | None = None,
) -> tuple[
    dict[str, tuple[IndicatorPoint, ...]],
    dict[str, DataQualityReport],
]:
    points_by_symbol: dict[str, tuple[IndicatorPoint, ...]] = {}
    quality_by_symbol: dict[str, DataQualityReport] = {}
    with CandleStore(database_path) as store:
        if not store.integrity_check():
            raise RuntimeError("SQLite integrity check failed")
        for symbol in SYMBOLS:
            actual_start = starts_by_symbol[symbol] if starts_by_symbol is not None else start
            if actual_start < start or actual_start >= end_exclusive:
                raise ValueError(f"{symbol}: invalid available history window")
            candles = store.load_candles(
                symbol,
                start=actual_start,
                end_exclusive=end_exclusive,
            )
            quality = audit_candles(
                candles,
                expected_symbol=symbol,
                expected_start=actual_start,
                expected_end_exclusive=end_exclusive,
            )
            quality.require_valid()
            if len(candles) <= strategy.parameters_for(symbol).warmup_bars:
                raise ValueError(f"{symbol}: insufficient history after strategy warm-up")
            points_by_symbol[symbol] = tuple(
                evaluate_batch(
                    symbol,
                    candles,
                    parameters=strategy.parameters_for(symbol),
                    semantics=strategy.semantics,
                    strategy_version=strategy.version,
                )
            )
            quality_by_symbol[symbol] = quality
    return points_by_symbol, quality_by_symbol

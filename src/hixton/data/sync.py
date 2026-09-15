"""Incremental, gap-aware market-data synchronization service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from hixton.constants import TIMEFRAME_DELTA
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import DataQualityReport, audit_candles
from hixton.data.storage import CandleStore, StoredSymbolRules, StoreResult


@dataclass(frozen=True, slots=True)
class DataSyncResult:
    symbol: str
    fetched: int
    inserted: int
    unchanged: int
    revised: int
    quality: DataQualityReport


def _missing_ranges(
    candles_open_times: list[datetime],
    *,
    start: datetime,
    end_exclusive: datetime,
) -> list[tuple[datetime, datetime]]:
    ranges: list[tuple[datetime, datetime]] = []
    cursor = start
    for open_time in sorted(set(candles_open_times)):
        if open_time < start or open_time >= end_exclusive:
            continue
        if open_time > cursor:
            ranges.append((cursor, open_time))
        cursor = max(cursor, open_time + TIMEFRAME_DELTA)
    if cursor < end_exclusive:
        ranges.append((cursor, end_exclusive))
    return ranges


def _merge_ranges(ranges: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for start, end in ordered[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def synchronize_symbol(
    *,
    client: BinancePublicClient,
    store: CandleStore,
    symbol: str,
    start: datetime,
    end_exclusive: datetime,
    full_refresh: bool = False,
    refresh_tail: timedelta = timedelta(hours=48),
) -> DataSyncResult:
    """Fill all gaps and refresh the recent tail before a strict final audit."""

    normalized = symbol.replace("/", "").upper()
    rules = client.symbol_rules(normalized)
    store.put_symbol_rules(
        StoredSymbolRules(
            symbol=rules.symbol,
            status=rules.status,
            quote_asset=rules.quote_asset,
            spot_allowed=rules.spot_allowed,
            order_types=rules.order_types,
            tick_size=rules.tick_size,
            step_size=rules.step_size,
            min_qty=rules.min_qty,
            min_notional=rules.min_notional,
            checked_at_utc=datetime.now(UTC),
        )
    )
    if not rules.tradable_for_v1:
        raise ValueError(f"{normalized} is not tradable for Binance Spot V1")

    local = store.load_candles(
        normalized,
        start=start,
        end_exclusive=end_exclusive,
        closed_only=False,
    )
    ranges = (
        [(start, end_exclusive)]
        if full_refresh
        else _missing_ranges(
            [candle.open_time_utc for candle in local],
            start=start,
            end_exclusive=end_exclusive,
        )
    )
    tail_start = max(start, end_exclusive - refresh_tail)
    if not full_refresh and (tail_start, end_exclusive) not in ranges:
        ranges.append((tail_start, end_exclusive))

    fetched = 0
    inserted = 0
    unchanged = 0
    revised = 0
    for range_start, range_end in _merge_ranges(ranges):
        candles = client.fetch_klines(
            normalized,
            start=range_start,
            end_exclusive=range_end,
        )
        fetched += len(candles)
        result: StoreResult = store.put_candles(candles)
        inserted += result.inserted
        unchanged += result.unchanged
        revised += result.revised

    final = store.load_candles(
        normalized,
        start=start,
        end_exclusive=end_exclusive,
    )
    quality = audit_candles(
        final,
        expected_symbol=normalized,
        expected_start=start,
        expected_end_exclusive=end_exclusive,
    )
    quality.require_valid()
    return DataSyncResult(
        symbol=normalized,
        fetched=fetched,
        inserted=inserted,
        unchanged=unchanged,
        revised=revised,
        quality=quality,
    )

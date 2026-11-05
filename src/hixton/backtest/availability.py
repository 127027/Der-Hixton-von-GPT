"""Real, staggered market history for a fixed reporting window; no invented bars."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from itertools import pairwise

from hixton.constants import TIMEFRAME_DELTA
from hixton.data.quality import audit_candles
from hixton.domain.models import Candle


def audit_observed(
    candles: list[Candle], symbol: str, start: datetime, end: datetime, *, allow_gaps: bool
) -> None:
    """Retain all quality gates except explicitly modelled internal missing hours."""
    report = audit_candles(
        candles, expected_symbol=symbol, expected_start=start, expected_end_exclusive=end
    )
    if allow_gaps:
        report = replace(
            report,
            issues=tuple(
                issue for issue in report.issues if issue.code not in {"GAP", "COUNT_MISMATCH"}
            ),
        )
    report.require_valid()


def global_gap_hours(series: dict[str, list[Candle]]) -> tuple[datetime, ...]:
    """Model only synchronized outages of every already available market."""
    missing: dict[str, set[datetime]] = {}
    for symbol, candles in series.items():
        hours: set[datetime] = set()
        for previous, current in pairwise(candles):
            at = previous.open_time_utc + TIMEFRAME_DELTA
            while at < current.open_time_utc:
                hours.add(at)
                at += TIMEFRAME_DELTA
        missing[symbol] = hours
    gaps = set().union(*missing.values())
    for at in sorted(gaps):
        for symbol, candles in series.items():
            if candles and candles[0].open_time_utc <= at and at not in missing[symbol]:
                raise ValueError(f"{symbol}: inconsistent market data GAP at {at.isoformat()}")
    return tuple(sorted(gaps))


def available_rows(
    series: dict[str, list[Candle]], start: datetime, end: datetime
) -> Iterator[tuple[datetime, tuple[Candle, ...]]]:
    """Yield each UTC hour, including cash-only hours before a market exists.

    Callers validate actual bars and synchronized outage policy first.
    """
    offsets = dict.fromkeys(series, 0)
    at = start
    while at < end:
        row = []
        for symbol, candles in series.items():
            offset = offsets[symbol]
            if offset < len(candles) and candles[offset].open_time_utc == at:
                row.append(candles[offset])
                offsets[symbol] += 1
        yield at, tuple(row)
        at += TIMEFRAME_DELTA

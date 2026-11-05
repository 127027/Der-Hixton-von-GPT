"""Real, staggered market history for a fixed reporting window; no invented bars."""

from collections.abc import Iterator
from datetime import datetime

from hixton.constants import TIMEFRAME_DELTA
from hixton.domain.models import Candle


def available_rows(
    series: dict[str, list[Candle]], start: datetime, end: datetime
) -> Iterator[tuple[datetime, tuple[Candle, ...]]]:
    """Yield each UTC hour, including cash-only hours before a market exists.

    Callers validate every actual series for internal/trailing gaps first.
    Only leading absence and an entirely unavailable symbol are permitted.
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

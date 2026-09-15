"""Deterministic candle-quality checks required before strategy evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from hixton.constants import TIMEFRAME_DELTA
from hixton.domain.models import Candle


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    code: str
    message: str
    open_time_utc: datetime | None = None


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    symbol: str
    candle_count: int
    first_open_time_utc: datetime | None
    last_open_time_utc: datetime | None
    expected_count: int | None
    issues: tuple[DataQualityIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def gap_count(self) -> int:
        return sum(issue.code == "GAP" for issue in self.issues)

    def require_valid(self) -> None:
        if not self.valid:
            summary = "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues[:5])
            raise ValueError(f"data quality failed for {self.symbol}: {summary}")


def audit_candles(
    candles: list[Candle],
    *,
    expected_symbol: str,
    interval: timedelta = TIMEFRAME_DELTA,
    expected_start: datetime | None = None,
    expected_end_exclusive: datetime | None = None,
) -> DataQualityReport:
    """Audit sequence without modifying, sorting or filling provider data."""

    symbol = expected_symbol.replace("/", "").upper()
    issues: list[DataQualityIssue] = []
    first = candles[0].open_time_utc if candles else None
    last = candles[-1].open_time_utc if candles else None

    if not candles:
        issues.append(DataQualityIssue("EMPTY", "no candles supplied"))

    seen: set[datetime] = set()
    previous: Candle | None = None
    for candle in candles:
        if candle.symbol != symbol:
            issues.append(
                DataQualityIssue(
                    "SYMBOL_MISMATCH",
                    f"expected {symbol}, got {candle.symbol}",
                    candle.open_time_utc,
                )
            )
        if candle.open_time_utc in seen:
            issues.append(
                DataQualityIssue("DUPLICATE", "duplicate open time", candle.open_time_utc)
            )
        seen.add(candle.open_time_utc)
        if not candle.closed:
            issues.append(
                DataQualityIssue("PROVISIONAL", "candle is not final", candle.open_time_utc)
            )
        if not candle.ohlc_is_valid:
            issues.append(
                DataQualityIssue(
                    "INVALID_OHLCV",
                    "OHLCV rule failed",
                    candle.open_time_utc,
                )
            )
        if previous is not None:
            expected_next = previous.open_time_utc + interval
            if candle.open_time_utc < previous.open_time_utc:
                issues.append(
                    DataQualityIssue(
                        "OUT_OF_ORDER",
                        "open times are not ascending",
                        candle.open_time_utc,
                    )
                )
            elif candle.open_time_utc != expected_next:
                issues.append(
                    DataQualityIssue(
                        "GAP",
                        (
                            f"expected {expected_next.isoformat()}, "
                            f"got {candle.open_time_utc.isoformat()}"
                        ),
                        candle.open_time_utc,
                    )
                )
        previous = candle

    expected_count: int | None = None
    if expected_start is not None and expected_end_exclusive is not None:
        duration = expected_end_exclusive - expected_start
        if duration.total_seconds() < 0 or duration % interval != timedelta(0):
            issues.append(
                DataQualityIssue(
                    "INVALID_WINDOW",
                    "expected window is not interval-aligned",
                )
            )
        else:
            expected_count = int(duration / interval)
            if len(candles) != expected_count:
                issues.append(
                    DataQualityIssue(
                        "COUNT_MISMATCH",
                        f"expected {expected_count} candles, got {len(candles)}",
                    )
                )
            if candles and candles[0].open_time_utc != expected_start:
                issues.append(
                    DataQualityIssue(
                        "START_MISMATCH",
                        (
                            f"expected {expected_start.isoformat()}, "
                            f"got {candles[0].open_time_utc.isoformat()}"
                        ),
                        candles[0].open_time_utc,
                    )
                )
            expected_last = expected_end_exclusive - interval
            if candles and candles[-1].open_time_utc != expected_last:
                issues.append(
                    DataQualityIssue(
                        "END_MISMATCH",
                        f"expected last {expected_last.isoformat()}, "
                        f"got {candles[-1].open_time_utc.isoformat()}",
                        candles[-1].open_time_utc,
                    )
                )

    return DataQualityReport(
        symbol=symbol,
        candle_count=len(candles),
        first_open_time_utc=first,
        last_open_time_utc=last,
        expected_count=expected_count,
        issues=tuple(issues),
    )

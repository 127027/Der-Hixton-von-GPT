"""Thread-safe runtime and strategy-analysis state shared with the local API."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from hixton.constants import SYMBOLS
from hixton.data.quality import DataQualityReport
from hixton.domain.models import Candle, IndicatorPoint


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    health: str
    mode: str
    message: str
    started_at_utc: datetime
    last_sync_utc: datetime | None
    last_stream_update_utc: datetime | None
    stream_connected: bool
    feed_mode: str
    next_daily_audit_utc: datetime | None
    last_daily_audit_utc: datetime | None
    last_error: str | None
    sync_in_progress: bool
    backtest_status: str


@dataclass(frozen=True, slots=True)
class RuntimeLog:
    time_utc: datetime
    level: str
    component: str
    event_code: str
    correlation_id: str
    mode: str
    message: str


@dataclass(slots=True)
class RuntimeState:
    health: str = "STARTING"
    mode: str = "PAPER"
    message: str = "Startup-Pruefungen laufen"
    started_at_utc: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_sync_utc: datetime | None = None
    last_stream_update_utc: datetime | None = None
    stream_connected: bool = False
    feed_mode: str = "REST_STARTUP"
    next_daily_audit_utc: datetime | None = None
    last_daily_audit_utc: datetime | None = None
    last_error: str | None = None
    sync_in_progress: bool = False
    backtest_status: str = "IDLE"
    _points: dict[str, tuple[IndicatorPoint, ...]] = field(default_factory=dict)
    _quality: dict[str, DataQualityReport] = field(default_factory=dict)
    _live_candles: dict[str, tuple[Candle, datetime]] = field(default_factory=dict)
    _logs: deque[RuntimeLog] = field(default_factory=lambda: deque(maxlen=2_000))
    _lock: RLock = field(default_factory=RLock)

    def __post_init__(self) -> None:
        self.log(
            level="INFO",
            component="runtime",
            event_code="PROCESS_START",
            message="Hixton-Prozess gestartet; Startup-Pruefungen laufen",
        )

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            return RuntimeSnapshot(
                health=self.health,
                mode=self.mode,
                message=self.message,
                started_at_utc=self.started_at_utc,
                last_sync_utc=self.last_sync_utc,
                last_stream_update_utc=self.last_stream_update_utc,
                stream_connected=self.stream_connected,
                feed_mode=self.feed_mode,
                next_daily_audit_utc=self.next_daily_audit_utc,
                last_daily_audit_utc=self.last_daily_audit_utc,
                last_error=self.last_error,
                sync_in_progress=self.sync_in_progress,
                backtest_status=self.backtest_status,
            )

    def set_status(self, **values: object) -> None:
        allowed = {
            "health",
            "mode",
            "message",
            "last_sync_utc",
            "last_stream_update_utc",
            "stream_connected",
            "feed_mode",
            "next_daily_audit_utc",
            "last_daily_audit_utc",
            "last_error",
            "sync_in_progress",
            "backtest_status",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown runtime state fields: {sorted(unknown)}")
        with self._lock:
            previous = (self.health, self.message, self.feed_mode, self.last_error)
            for name, value in values.items():
                setattr(self, name, value)
            current = (self.health, self.message, self.feed_mode, self.last_error)
            if current != previous:
                level = (
                    "ERROR"
                    if self.health == "HALTED"
                    else ("WARNING" if self.health == "DEGRADED" or self.last_error else "INFO")
                )
                message = self.message
                if self.last_error is not None:
                    message = f"{message}: {self.last_error}"
                self._logs.append(
                    RuntimeLog(
                        time_utc=datetime.now(UTC),
                        level=level,
                        component="runtime",
                        event_code="RUNTIME_STATE_CHANGED",
                        correlation_id=str(uuid4()),
                        mode=self.mode,
                        message=message,
                    )
                )

    def log(
        self,
        *,
        level: str,
        component: str,
        event_code: str,
        message: str,
    ) -> None:
        with self._lock:
            self._logs.append(
                RuntimeLog(
                    time_utc=datetime.now(UTC),
                    level=level,
                    component=component,
                    event_code=event_code,
                    correlation_id=str(uuid4()),
                    mode=self.mode,
                    message=message,
                )
            )

    def logs(self, *, limit: int = 250) -> tuple[RuntimeLog, ...]:
        if limit <= 0 or limit > 2_000:
            raise ValueError("runtime log limit must be between 1 and 2000")
        with self._lock:
            return tuple(reversed(tuple(self._logs)[-limit:]))

    def replace_analysis(
        self,
        points: dict[str, tuple[IndicatorPoint, ...]],
        quality: dict[str, DataQualityReport],
    ) -> None:
        if set(points) != set(SYMBOLS) or set(quality) != set(SYMBOLS):
            raise ValueError("analysis cache requires all ten DMS symbols")
        with self._lock:
            self._points = dict(points)
            self._quality = dict(quality)

    def points(self) -> dict[str, tuple[IndicatorPoint, ...]]:
        with self._lock:
            return dict(self._points)

    def set_live_candle(self, candle: Candle, *, at: datetime | None = None) -> None:
        with self._lock:
            previous = self._live_candles.get(candle.symbol)
            if previous is None or candle.open_time_utc >= previous[0].open_time_utc:
                self._live_candles[candle.symbol] = (candle, at or datetime.now(UTC))

    def live_candle(
        self, symbol: str, *, now: datetime | None = None
    ) -> tuple[Candle, datetime] | None:
        with self._lock:
            item = self._live_candles.get(symbol)
            age = ((now or datetime.now(UTC)) - item[1]).total_seconds() if item else 91
            return item if 0 <= age <= 90 else None

    def quality(self) -> dict[str, DataQualityReport]:
        with self._lock:
            return dict(self._quality)

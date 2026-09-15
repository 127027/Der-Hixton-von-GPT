"""Immutable domain models shared by batch, replay, paper and live modes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


class TrendState(StrEnum):
    UNINITIALIZED = "UNINITIALIZED"
    DOWN = "DOWN"
    UP = "UP"


class SignalAction(StrEnum):
    ENTER_LONG = "ENTER_LONG"
    EXIT_LONG = "EXIT_LONG"


class StrategySemantics(StrEnum):
    DMS_V1 = "DMS_V1"
    PINE_V6 = "PINE_V6"


@dataclass(frozen=True, slots=True)
class Candle:
    """One provider candle. Numeric OHLCV fields intentionally use Binary64."""

    symbol: str
    open_time_utc: datetime
    close_time_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trade_count: int = 0
    closed: bool = True
    source: str = "binance_spot"

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.replace("/", "").upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "open_time_utc", _as_utc(self.open_time_utc, "open_time_utc"))
        object.__setattr__(self, "close_time_utc", _as_utc(self.close_time_utc, "close_time_utc"))
        if self.close_time_utc <= self.open_time_utc:
            raise ValueError("close_time_utc must be after open_time_utc")

    @property
    def values_are_finite(self) -> bool:
        return all(
            isfinite(value)
            for value in (
                self.open,
                self.high,
                self.low,
                self.close,
                self.volume,
                self.quote_volume,
            )
        )

    @property
    def ohlc_is_valid(self) -> bool:
        return (
            self.values_are_finite
            and min(self.open, self.high, self.low, self.close) > 0.0
            and self.high >= max(self.open, self.close, self.low)
            and self.low <= min(self.open, self.close, self.high)
            and self.volume >= 0.0
            and self.quote_volume >= 0.0
            and self.trade_count >= 0
        )


@dataclass(frozen=True, slots=True)
class StrategyParameters:
    vidya_length: int = 10
    momentum_length: int = 20
    smoothing_length: int = 15
    atr_length: int = 200
    band_multiplier: float = 2.0
    warmup_bars: int = 400

    def __post_init__(self) -> None:
        integer_values = (
            self.vidya_length,
            self.momentum_length,
            self.smoothing_length,
            self.atr_length,
            self.warmup_bars,
        )
        if any(value <= 0 for value in integer_values):
            raise ValueError("all strategy lengths must be positive")
        if self.warmup_bars < self.atr_length:
            raise ValueError("warmup_bars must cover atr_length")
        if self.band_multiplier <= 0.0:
            raise ValueError("band_multiplier must be positive")


@dataclass(frozen=True, slots=True)
class IndicatorPoint:
    symbol: str
    strategy_version: str
    index: int
    candle: Candle
    abs_cmo: float | None
    vidya_raw: float | None
    vidya: float | None
    true_range: float
    atr: float | None
    upper: float | None
    lower: float | None
    trend: TrendState
    flip_up: bool
    flip_down: bool
    breakout_strength: float | None
    rank_strength: float | None
    tradable: bool


@dataclass(frozen=True, slots=True)
class Signal:
    signal_id: str
    symbol: str
    action: SignalAction
    candle_close_time_utc: datetime
    strategy_version: str
    point_index: int
    close: float
    upper: float
    lower: float
    atr: float
    breakout_strength: float | None

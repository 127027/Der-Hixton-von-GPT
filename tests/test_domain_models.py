from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from hixton.domain.models import Candle, StrategyParameters


def _candle() -> Candle:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="eth/usdc",
        open_time_utc=start,
        close_time_utc=start + timedelta(hours=1) - timedelta(milliseconds=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=10.0,
    )


def test_candle_normalizes_symbol_and_validates_ohlcv() -> None:
    candle = _candle()
    assert candle.symbol == "ETHUSDC"
    assert candle.ohlc_is_valid
    assert not replace(candle, high=100.5).ohlc_is_valid
    assert not replace(candle, volume=-1.0).ohlc_is_valid


def test_candle_requires_aware_increasing_times() -> None:
    candle = _candle()
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(candle, open_time_utc=datetime(2025, 1, 1))
    with pytest.raises(ValueError, match="after"):
        replace(candle, close_time_utc=candle.open_time_utc)


def test_strategy_parameter_guards() -> None:
    assert StrategyParameters().warmup_bars == 400
    with pytest.raises(ValueError, match="positive"):
        StrategyParameters(momentum_length=0)
    with pytest.raises(ValueError, match="cover"):
        StrategyParameters(warmup_bars=100)

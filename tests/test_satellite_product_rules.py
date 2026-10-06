from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from hixton.domain.models import Candle, IndicatorPoint, StrategySemantics, TrendState
from hixton.domain.satellite_layer import (
    ACTIVE_SHARED_SATELLITES,
    shared_satellite_entry_block_reason,
    shared_satellite_horizon_exit,
)


def _point(
    symbol: str,
    *,
    close_time: datetime,
    close: float = 100.0,
    atr: float = 1.0,
    vidya: float = 99.0,
) -> IndicatorPoint:
    return IndicatorPoint(
        symbol=symbol,
        strategy_version="TEST-SATELLITE",
        index=1,
        candle=Candle(
            symbol=symbol,
            open_time_utc=close_time - timedelta(hours=1),
            close_time_utc=close_time,
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1,
        ),
        abs_cmo=0.5,
        vidya_raw=vidya,
        vidya=vidya,
        true_range=atr,
        atr=atr,
        upper=close + 2,
        lower=close - 2,
        trend=TrendState.UP,
        flip_up=True,
        flip_down=False,
        breakout_strength=1.0,
        rank_strength=1.0,
        tradable=True,
    )


def test_only_near_and_bch_are_active_shared_satellites() -> None:
    assert ACTIVE_SHARED_SATELLITES == ("NEARUSDC", "BCHUSDC")


def test_bch_shared_entry_filter_is_point_in_time_atr_regime() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    accepted = _point("BCHUSDC", close_time=now, close=100, atr=1.99)
    rejected = replace(accepted, atr=2.01)
    assert shared_satellite_entry_block_reason("BCHUSDC", accepted) is None
    assert (
        shared_satellite_entry_block_reason("BCHUSDC", rejected)
        == "SATELLITE_ATR_TOO_HIGH"
    )


def test_inactive_satellite_is_research_only() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert (
        shared_satellite_entry_block_reason(
            "AAVEUSDC",
            _point("AAVEUSDC", close_time=now),
        )
        == "SATELLITE_RESEARCH_ONLY"
    )


def test_near_horizon_exit_uses_only_closed_bar_age() -> None:
    entry = datetime(2026, 1, 1, 0, tzinfo=UTC)
    before = _point(
        "NEARUSDC",
        close_time=entry + timedelta(hours=47, minutes=59),
    )
    at_horizon = _point(
        "NEARUSDC",
        close_time=entry + timedelta(hours=48),
    )
    assert (
        shared_satellite_horizon_exit(
            "NEARUSDC",
            before,
            entry_time_utc=entry,
        )
        is None
    )
    signal = shared_satellite_horizon_exit(
        "NEARUSDC",
        at_horizon,
        entry_time_utc=entry,
    )
    assert signal is not None
    assert signal.candle_close_time_utc == at_horizon.candle.close_time_utc
    assert signal.strategy_version == "TEST-SATELLITE"

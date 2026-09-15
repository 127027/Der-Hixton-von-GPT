from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hixton.domain.strategy import evaluate_batch
from hixton.ui.chart import build_chart_payload, range_start
from tests.golden_reference import deterministic_candles


def test_today_uses_selected_timezone_midnight() -> None:
    now = datetime(2026, 7, 1, 10, 30, tzinfo=UTC)
    assert range_start("today", now=now, timezone_name="Europe/Berlin") == datetime(
        2026, 6, 30, 22, 0, tzinfo=UTC
    )
    assert range_start("today", now=now, timezone_name="UTC") == datetime(
        2026, 7, 1, 0, 0, tzinfo=UTC
    )


def test_one_year_is_display_only_four_hour_aggregation() -> None:
    candles = deterministic_candles("BTCUSDC", 500)
    points = tuple(evaluate_batch("BTCUSDC", candles))
    now = candles[-1].close_time_utc + timedelta(milliseconds=1)
    payload = build_chart_payload(
        symbol="BTCUSDC",
        points=points,
        range_key="1y",
        timezone_name="Europe/Berlin",
        now=now,
    )
    assert payload["trading_timeframe"] == "1h"
    assert payload["display_resolution"] == "4h"
    bars = payload["bars"]
    assert isinstance(bars, list)
    assert len(bars) == 125
    assert all(bar["native_bar_count"] == 4 for bar in bars)


def test_three_year_signal_markers_align_to_daily_display_bars() -> None:
    candles = deterministic_candles("ETHUSDC", 1_200)
    points = tuple(evaluate_batch("ETHUSDC", candles))
    now = candles[-1].close_time_utc + timedelta(milliseconds=1)
    payload = build_chart_payload(
        symbol="ETHUSDC",
        points=points,
        range_key="3y",
        timezone_name="UTC",
        now=now,
    )
    bars = payload["bars"]
    signals = payload["signals"]
    assert isinstance(bars, list)
    assert isinstance(signals, list)
    bar_times = {bar["time"] for bar in bars}
    assert signals
    assert all(signal["display_time"] in bar_times for signal in signals)

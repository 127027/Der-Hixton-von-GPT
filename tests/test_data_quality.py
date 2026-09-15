from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from hixton.data.quality import audit_candles
from tests.golden_reference import deterministic_candles


def test_complete_sequence_passes_exact_window_audit() -> None:
    candles = deterministic_candles("ETHUSDC", 500, 1)
    report = audit_candles(
        candles,
        expected_symbol="ETHUSDC",
        expected_start=candles[0].open_time_utc,
        expected_end_exclusive=candles[-1].open_time_utc + timedelta(hours=1),
    )
    assert report.valid
    assert report.expected_count == 500
    assert report.gap_count == 0


def test_gap_duplicate_provisional_and_bad_ohlcv_are_reported() -> None:
    candles = deterministic_candles("BTCUSDC", 5)
    broken = [
        candles[0],
        replace(candles[1], closed=False),
        replace(candles[1], closed=False),
        replace(candles[3], high=candles[3].low - 1.0),
        candles[4],
    ]
    report = audit_candles(broken, expected_symbol="BTCUSDC")
    codes = {issue.code for issue in report.issues}
    assert {"PROVISIONAL", "DUPLICATE", "GAP", "INVALID_OHLCV"} <= codes
    assert not report.valid


def test_symbol_and_window_boundaries_are_not_silently_corrected() -> None:
    candles = deterministic_candles("SOLUSDC", 3, 3)
    candles[1] = replace(candles[1], symbol="ETHUSDC")
    report = audit_candles(
        candles,
        expected_symbol="SOLUSDC",
        expected_start=candles[0].open_time_utc - timedelta(hours=1),
        expected_end_exclusive=candles[-1].open_time_utc + timedelta(hours=1),
    )
    codes = {issue.code for issue in report.issues}
    assert {"SYMBOL_MISMATCH", "COUNT_MISMATCH", "START_MISMATCH"} <= codes

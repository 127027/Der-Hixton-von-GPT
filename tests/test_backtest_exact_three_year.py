from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from hixton import cli
from hixton.domain.models import Candle
from hixton.runtime import analysis
from hixton.runtime.supervisor import safe_closed_window


class _ValidAudit:
    def require_valid(self) -> None:
        return None


def _candle(symbol: str, open_time: datetime) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_utc=open_time,
        close_time_utc=open_time + timedelta(hours=1),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )


def test_cli_window_is_exactly_three_calendar_years_plus_400_warmup_hours() -> None:
    end = datetime(2026, 9, 19, 19, tzinfo=UTC)
    warmup, start, actual_end = cli._window(end)
    assert actual_end == end
    assert start == datetime(2023, 9, 19, 19, tzinfo=UTC)
    assert warmup == start - timedelta(hours=400)


def test_ui_runtime_window_is_exactly_three_calendar_years_plus_warmup() -> None:
    now = datetime(2026, 9, 19, 19, 37, tzinfo=UTC)
    warmup, start, end = safe_closed_window(now)
    assert end == datetime(2026, 9, 19, 19, tzinfo=UTC)
    assert start == datetime(2023, 9, 19, 19, tzinfo=UTC)
    assert warmup == start - timedelta(hours=400)


def test_available_report_start_fails_closed_instead_of_shortening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = datetime(2023, 9, 19, 19, tzinfo=UTC)
    end = datetime(2026, 9, 19, 19, tzinfo=UTC)
    # One warm-up hour is missing: a former implementation silently shortened
    # the report window by one hour. The product contract now rejects it.
    first = requested - timedelta(hours=399)
    monkeypatch.setattr(analysis, "audit_candles", lambda *args, **kwargs: _ValidAudit())
    with pytest.raises(ValueError, match="exact three-year history"):
        analysis.available_report_start(
            {"BTCUSDC": [_candle("BTCUSDC", first)]},
            requested,
            end,
        )


def test_available_report_start_keeps_requested_start_when_full_warmup_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = datetime(2023, 9, 19, 19, tzinfo=UTC)
    end = datetime(2026, 9, 19, 19, tzinfo=UTC)
    first = requested - timedelta(hours=400)
    monkeypatch.setattr(analysis, "audit_candles", lambda *args, **kwargs: _ValidAudit())
    assert (
        analysis.available_report_start(
            {"BTCUSDC": [_candle("BTCUSDC", first)]},
            requested,
            end,
        )
        == requested
    )

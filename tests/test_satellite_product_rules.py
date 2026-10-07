from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from hixton.domain.models import Candle, IndicatorPoint, TrendState
from hixton.domain.satellite_layer import (
    ACTIVE_SHARED_SATELLITES,
    SATELLITE_PROFILES,
    SATELLITE_SYMBOLS,
    satellite_entry_point,
    satellite_handoff_symbols,
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


def test_all_five_fillers_share_bounded_entry_and_exit_rules() -> None:
    assert ACTIVE_SHARED_SATELLITES == ("NEARUSDC", "AAVEUSDC", "BCHUSDC")
    assert set(ACTIVE_SHARED_SATELLITES) < set(SATELLITE_SYMBOLS)
    assert all(p.entry_interval_hours == 12 for p in SATELLITE_PROFILES)
    assert {p.symbol: p.horizon_hours for p in SATELLITE_PROFILES} == {
        "SUIUSDC": 0, "NEARUSDC": 48, "UNIUSDC": 0, "AAVEUSDC": 120, "BCHUSDC": 0,
    }


def test_bch_shared_entry_filter_is_point_in_time_atr_regime() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    accepted = _point("BCHUSDC", close_time=now, close=100, atr=1.99)
    rejected = replace(accepted, atr=2.01)
    assert shared_satellite_entry_block_reason("BCHUSDC", accepted) is None
    assert shared_satellite_entry_block_reason("BCHUSDC", rejected) == "SATELLITE_ATR_TOO_HIGH"


def test_unregistered_market_cannot_allocate_filler_capital() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert (
        shared_satellite_entry_block_reason(
            "UNKNOWNUSDC",
            _point("UNKNOWNUSDC", close_time=now),
        )
        == "SATELLITE_RESEARCH_ONLY"
    )


def test_negative_shared_fillers_remain_research_only() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    for symbol in ("SUIUSDC", "UNIUSDC"):
        assert (
            shared_satellite_entry_block_reason(symbol, _point(symbol, close_time=now))
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


def test_continuation_entry_requires_closed_scheduled_uptrend_and_preserves_core() -> None:
    point = replace(
        _point("NEARUSDC", close_time=datetime(2026, 1, 1, 12, tzinfo=UTC)),
        flip_up=False,
        strategy_version="HIXTON-V8-TEST",
    )
    assert satellite_entry_point(point).flip_up
    assert not point.flip_up
    assert satellite_entry_point(replace(point, trend=TrendState.DOWN)) == replace(
        point, trend=TrendState.DOWN
    )
    provisional = replace(point, candle=replace(point.candle, closed=False))
    assert satellite_entry_point(provisional) == provisional
    unscheduled = replace(
        point,
        candle=replace(
            point.candle,
            open_time_utc=point.candle.open_time_utc + timedelta(hours=1),
            close_time_utc=point.candle.close_time_utc + timedelta(hours=1),
        ),
    )
    assert satellite_entry_point(unscheduled) == unscheduled
    core = replace(point, symbol="BTCUSDC")
    assert satellite_entry_point(core) == core


def test_core_handoff_reclaims_all_fillers_and_credits_planned_exits() -> None:
    args = {
        "position_slots": {"NEARUSDC": 1, "BCHUSDC": 1},
        "active_satellites": frozenset(ACTIVE_SHARED_SATELLITES),
        "slot_count": 2,
    }
    assert satellite_handoff_symbols(core_entry_count=0, **args) == ()
    assert satellite_handoff_symbols(core_entry_count=1, **args) == ("BCHUSDC", "NEARUSDC")
    assert satellite_handoff_symbols(core_entry_count=2, **args) == ("BCHUSDC", "NEARUSDC")
    assert (
        satellite_handoff_symbols(
            core_entry_count=1, exiting_symbols=frozenset({"BCHUSDC"}), **args
        )
        == ("NEARUSDC",)
    )
    args["position_slots"] = {"NEARUSDC": 1}
    assert satellite_handoff_symbols(core_entry_count=1, **args) == ("NEARUSDC",)
    args["position_slots"] = {"BTCUSDC": 1, "NEARUSDC": 1}
    assert satellite_handoff_symbols(core_entry_count=1, **args) == ("NEARUSDC",)

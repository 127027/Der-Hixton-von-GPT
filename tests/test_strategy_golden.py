from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from hixton.constants import HIXTON_SPEC_VERSION, SYMBOLS
from hixton.domain.models import (
    SignalAction,
    StrategyParameters,
    StrategySemantics,
    TrendState,
)
from hixton.domain.strategy import HixtonStrategy, StrategyInputError, evaluate_batch, rank_strength
from tests.golden_reference import (
    deterministic_candles,
    independent_pine_v6_reference,
    independent_reference,
)


def _assert_close(actual: float | None, expected: float | None) -> None:
    if actual is None or expected is None:
        assert actual is expected
        return
    assert actual == pytest.approx(expected, abs=1e-10, rel=1e-9)


@pytest.mark.parametrize(("market_index", "symbol"), tuple(enumerate(SYMBOLS)))
def test_1200_bar_golden_parity_for_each_market(market_index: int, symbol: str) -> None:
    candles = deterministic_candles(symbol, 1_200, market_index)
    expected = independent_reference(candles)
    actual = evaluate_batch(symbol, candles)

    assert len(actual) == len(expected) == 1_200
    for point, reference in zip(actual, expected, strict=True):
        _assert_close(point.abs_cmo, reference.abs_cmo)
        _assert_close(point.vidya_raw, reference.vidya_raw)
        _assert_close(point.vidya, reference.vidya)
        _assert_close(point.true_range, reference.true_range)
        _assert_close(point.atr, reference.atr)
        _assert_close(point.upper, reference.upper)
        _assert_close(point.lower, reference.lower)
        assert point.trend is reference.trend
        assert point.flip_up is reference.flip_up
        assert point.flip_down is reference.flip_down

    assert sum(point.flip_up for point in actual) >= 2
    assert sum(point.flip_down for point in actual) >= 2


def test_initial_state_and_first_tradable_bar_are_exact() -> None:
    points = evaluate_batch("ETHUSDC", deterministic_candles("ETHUSDC", 401, 1))
    assert all(point.trend is TrendState.UNINITIALIZED for point in points[:399])
    assert points[399].trend is TrendState.DOWN
    assert not points[399].tradable
    assert points[400].tradable


def test_owner_pine_v6_semantics_match_independent_oracle() -> None:
    parameters = StrategyParameters(
        vidya_length=6,
        momentum_length=20,
        smoothing_length=8,
        atr_length=60,
        band_multiplier=3.8,
        warmup_bars=400,
    )
    candles = deterministic_candles("BTCUSDC", 1_200)
    expected = independent_pine_v6_reference(candles, parameters)
    actual = evaluate_batch(
        "BTCUSDC",
        candles,
        parameters=parameters,
        semantics=StrategySemantics.PINE_V6,
    )

    for point, reference in zip(actual, expected, strict=True):
        _assert_close(point.abs_cmo, reference.abs_cmo)
        _assert_close(point.vidya_raw, reference.vidya_raw)
        _assert_close(point.vidya, reference.vidya)
        _assert_close(point.true_range, reference.true_range)
        _assert_close(point.atr, reference.atr)
        _assert_close(point.upper, reference.upper)
        _assert_close(point.lower, reference.lower)
        assert point.trend is reference.trend
        assert point.flip_up is reference.flip_up
        assert point.flip_down is reference.flip_down

    assert all(point.trend is TrendState.DOWN for point in actual[:59])
    assert actual[0].vidya_raw == candles[0].close
    assert actual[1].vidya_raw is None
    assert not actual[399].tradable
    assert actual[400].tradable


def test_batch_and_bar_by_bar_replay_are_identical() -> None:
    candles = deterministic_candles("BTCUSDC", 1_000)
    batch = evaluate_batch("BTCUSDC", candles)
    replay_engine = HixtonStrategy("BTCUSDC")
    replay = [replay_engine.update(candle) for candle in candles]
    assert batch == replay


def test_signal_id_is_stable_and_position_aware() -> None:
    points = evaluate_batch("SOLUSDC", deterministic_candles("SOLUSDC", 1_200, 3))
    entry_point = next(point for point in points if point.flip_up)
    entry = HixtonStrategy.signal_for(entry_point, is_long=False)
    duplicate = HixtonStrategy.signal_for(entry_point, is_long=False)
    assert entry is not None
    assert duplicate == entry
    assert entry.strategy_version == HIXTON_SPEC_VERSION
    assert entry.action is SignalAction.ENTER_LONG
    assert HixtonStrategy.signal_for(entry_point, is_long=True) is None

    exit_point = next(point for point in points[entry_point.index + 1 :] if point.flip_down)
    exit_signal = HixtonStrategy.signal_for(exit_point, is_long=True)
    assert exit_signal is not None
    assert exit_signal.action is SignalAction.EXIT_LONG
    assert HixtonStrategy.signal_for(exit_point, is_long=False) is None


def test_provisional_invalid_and_gapped_candles_are_rejected() -> None:
    candle = deterministic_candles("BTCUSDC", 2)[0]
    engine = HixtonStrategy("BTCUSDC")
    with pytest.raises(StrategyInputError, match="provisional"):
        engine.update(replace(candle, closed=False))
    with pytest.raises(StrategyInputError, match="invalid OHLCV"):
        engine.update(replace(candle, low=-1.0))

    engine = HixtonStrategy("BTCUSDC")
    engine.update(candle)
    with pytest.raises(StrategyInputError, match="non-contiguous"):
        engine.update(
            replace(
                deterministic_candles("BTCUSDC", 2)[1],
                open_time_utc=candle.open_time_utc + timedelta(hours=2),
                close_time_utc=candle.close_time_utc + timedelta(hours=2),
            )
        )


def test_rank_strength_uses_half_even_at_twelve_decimals() -> None:
    assert rank_strength(0.1234567890124) == 0.123456789012
    assert rank_strength(0.1234567890126) == 0.123456789013

"""Independent formula oracle and deterministic candle fixtures for DMS V1 tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import cos, sin

from hixton.domain.models import Candle, StrategyParameters, TrendState


@dataclass(frozen=True, slots=True)
class ReferencePoint:
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


def independent_pine_v6_reference(
    candles: list[Candle], parameters: StrategyParameters
) -> list[ReferencePoint]:
    """Literal array oracle for the owner-supplied Pine v6 calculation semantics."""

    closes = [candle.close for candle in candles]
    positive: list[float] = []
    negative: list[float] = []
    raw_values: list[float | None] = []
    non_null_raw_values: list[float] = []
    true_ranges: list[float] = []
    atr_values: list[float | None] = []
    points: list[ReferencePoint] = []
    trend = TrendState.DOWN
    alpha = 2.0 / (parameters.vidya_length + 1.0)

    for index, candle in enumerate(candles):
        momentum = 0.0 if index == 0 else closes[index] - closes[index - 1]
        positive.append(max(momentum, 0.0))
        negative.append(max(-momentum, 0.0))
        abs_cmo: float | None = None
        if index >= parameters.momentum_length - 1:
            low_index = index - parameters.momentum_length + 1
            pos_sum = sum(positive[low_index : index + 1])
            neg_sum = sum(negative[low_index : index + 1])
            denominator = pos_sum + neg_sum
            abs_cmo = (
                0.0
                if denominator == 0.0
                else abs((pos_sum - neg_sum) / denominator)
            )

        previous_raw = raw_values[index - 1] if index else None
        if previous_raw is None:
            vidya_raw = candle.close
        elif abs_cmo is None:
            vidya_raw = None
        else:
            effective_alpha = alpha * abs_cmo
            vidya_raw = (
                effective_alpha * candle.close + (1.0 - effective_alpha) * previous_raw
            )
        raw_values.append(vidya_raw)
        if vidya_raw is not None:
            non_null_raw_values.append(vidya_raw)
        vidya = (
            sum(non_null_raw_values[-parameters.smoothing_length :])
            / parameters.smoothing_length
            if len(non_null_raw_values) >= parameters.smoothing_length
            else None
        )

        if index == 0:
            true_range = candle.high - candle.low
        else:
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - closes[index - 1]),
                abs(candle.low - closes[index - 1]),
            )
        true_ranges.append(true_range)
        atr: float | None = None
        if index == parameters.atr_length - 1:
            atr = sum(true_ranges[: parameters.atr_length]) / parameters.atr_length
        elif index >= parameters.atr_length:
            previous_atr = atr_values[index - 1]
            assert previous_atr is not None
            atr = (
                previous_atr * (parameters.atr_length - 1) + true_range
            ) / parameters.atr_length
        atr_values.append(atr)

        upper = (
            vidya + atr * parameters.band_multiplier
            if vidya is not None and atr is not None
            else None
        )
        lower = (
            vidya - atr * parameters.band_multiplier
            if vidya is not None and atr is not None
            else None
        )
        previous_trend = trend
        if index and upper is not None and lower is not None:
            previous_upper = points[index - 1].upper
            previous_lower = points[index - 1].lower
            if previous_upper is not None and previous_lower is not None:
                if candle.close > upper and closes[index - 1] <= previous_upper:
                    trend = TrendState.UP
                if candle.close < lower and closes[index - 1] >= previous_lower:
                    trend = TrendState.DOWN
        flip_up = previous_trend is TrendState.DOWN and trend is TrendState.UP
        flip_down = previous_trend is TrendState.UP and trend is TrendState.DOWN

        points.append(
            ReferencePoint(
                abs_cmo=abs_cmo,
                vidya_raw=vidya_raw,
                vidya=vidya,
                true_range=true_range,
                atr=atr,
                upper=upper,
                lower=lower,
                trend=trend,
                flip_up=flip_up,
                flip_down=flip_down,
            )
        )
    return points


def deterministic_candles(symbol: str, count: int, market_index: int = 0) -> list[Candle]:
    """Create stable, non-random 1h candles with several volatility regimes."""

    start = datetime(2022, 1, 1, tzinfo=UTC)
    base = 80.0 + market_index * 17.0
    previous_close = base
    candles: list[Candle] = []
    for index in range(count):
        cycle = index % 240
        if cycle < 60:
            regime = cycle * 0.24
        elif cycle < 120:
            regime = (120 - cycle) * 0.31 - 4.2
        elif cycle < 180:
            regime = -(cycle - 120) * 0.22
        else:
            regime = (cycle - 240) * 0.28 + 3.0
        close = (
            base
            + index * (0.003 + market_index * 0.0002)
            + regime
            + sin((index + market_index * 3) / 7.0) * 2.8
            + cos((index + market_index) / 19.0) * 1.4
        )
        open_price = previous_close
        wick = 0.55 + abs(sin((index + 5 * market_index) / 13.0)) * 0.7
        high = max(open_price, close) + wick
        low = min(open_price, close) - wick * 0.9
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol=symbol,
                open_time_utc=open_time,
                close_time_utc=open_time + timedelta(hours=1) - timedelta(milliseconds=1),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=1_000.0 + index * 0.5 + market_index * 10.0,
                quote_volume=(1_000.0 + index * 0.5) * close,
                trade_count=100 + index % 37,
            )
        )
        previous_close = close
    return candles


def independent_reference(candles: list[Candle]) -> list[ReferencePoint]:
    """Literal array-based implementation, intentionally separate from production state."""

    closes = [candle.close for candle in candles]
    positive: list[float] = []
    negative: list[float] = []
    raw_values: list[float] = []
    true_ranges: list[float] = []
    atr_values: list[float | None] = []
    points: list[ReferencePoint] = []
    trend = TrendState.UNINITIALIZED
    alpha = 2.0 / 11.0

    for index, candle in enumerate(candles):
        momentum = 0.0 if index == 0 else closes[index] - closes[index - 1]
        positive.append(max(momentum, 0.0))
        negative.append(max(-momentum, 0.0))
        low_index = max(1, index - 20 + 1)
        pos_sum = sum(positive[low_index : index + 1]) if index >= 1 else 0.0
        neg_sum = sum(negative[low_index : index + 1]) if index >= 1 else 0.0
        denominator = pos_sum + neg_sum
        abs_cmo = 0.0 if denominator == 0.0 else abs((pos_sum - neg_sum) / denominator)

        if index == 0:
            vidya_raw = candle.close
        else:
            effective_alpha = alpha * abs_cmo
            vidya_raw = (
                effective_alpha * candle.close + (1.0 - effective_alpha) * raw_values[index - 1]
            )
        raw_values.append(vidya_raw)
        vidya = sum(raw_values[index - 14 : index + 1]) / 15.0 if index >= 14 else None

        if index == 0:
            true_range = candle.high - candle.low
        else:
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - closes[index - 1]),
                abs(candle.low - closes[index - 1]),
            )
        true_ranges.append(true_range)
        atr: float | None = None
        if index == 199:
            atr = sum(true_ranges[:200]) / 200.0
        elif index >= 200:
            previous_atr = atr_values[index - 1]
            assert previous_atr is not None
            atr = (previous_atr * 199.0 + true_range) / 200.0
        atr_values.append(atr)

        upper = vidya + atr * 2.0 if vidya is not None and atr is not None else None
        lower = vidya - atr * 2.0 if vidya is not None and atr is not None else None
        flip_up = False
        flip_down = False
        if index == 399:
            trend = TrendState.DOWN
        elif index >= 400:
            previous_upper = points[index - 1].upper
            previous_lower = points[index - 1].lower
            assert upper is not None and lower is not None
            assert previous_upper is not None and previous_lower is not None
            flip_up = candle.close > upper and closes[index - 1] <= previous_upper
            flip_down = candle.close < lower and closes[index - 1] >= previous_lower
            if flip_up:
                trend = TrendState.UP
            elif flip_down:
                trend = TrendState.DOWN

        points.append(
            ReferencePoint(
                abs_cmo=abs_cmo,
                vidya_raw=vidya_raw,
                vidya=vidya,
                true_range=true_range,
                atr=atr,
                upper=upper,
                lower=lower,
                trend=trend,
                flip_up=flip_up,
                flip_down=flip_down,
            )
        )
    return points

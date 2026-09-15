"""Streaming and batch implementation of DMS strategy HIXTON-SPEC-1.0."""

from __future__ import annotations

import hashlib
from collections import deque
from collections.abc import Iterable, Sequence
from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from hixton.constants import (
    HIXTON_SPEC_VERSION,
    HIXTON_V2_RESEARCH_VERSION,
    TIMEFRAME_DELTA,
)
from hixton.domain.models import (
    Candle,
    IndicatorPoint,
    Signal,
    SignalAction,
    StrategyParameters,
    StrategySemantics,
    TrendState,
)

_RANK_QUANTUM = Decimal("0.000000000001")


class StrategyInputError(ValueError):
    """Raised when a candle sequence is unsafe for strategy evaluation."""


def rank_strength(value: float) -> float:
    """Round breakout strength to 12 decimals using round-half-even."""

    return float(Decimal(str(value)).quantize(_RANK_QUANTUM, rounding=ROUND_HALF_EVEN))


def entry_priority(
    strength: float | None, symbol: str, symbols: Sequence[str]
) -> tuple[float, int]:
    """One deterministic priority rule for historical, Paper and real-order candidates."""
    return -rank_strength(strength or 0.0), symbols.index(symbol)


def _signal_id(point: IndicatorPoint, action: SignalAction) -> str:
    identity = "|".join(
        (
            point.strategy_version,
            point.symbol,
            point.candle.close_time_utc.isoformat(),
            action.value,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class HixtonStrategy:
    """Stateful one-symbol strategy evaluator with no external dependencies."""

    def __init__(
        self,
        symbol: str,
        parameters: StrategyParameters | None = None,
        expected_interval: timedelta = TIMEFRAME_DELTA,
        semantics: StrategySemantics = StrategySemantics.DMS_V1,
        strategy_version: str | None = None,
    ) -> None:
        self.symbol = symbol.replace("/", "").upper()
        self.parameters = parameters or StrategyParameters()
        self.expected_interval = expected_interval
        self.semantics = semantics
        self.strategy_version = strategy_version or (
            HIXTON_V2_RESEARCH_VERSION
            if semantics is StrategySemantics.PINE_V6
            else HIXTON_SPEC_VERSION
        )
        self._positive: deque[float] = deque(maxlen=self.parameters.momentum_length)
        self._negative: deque[float] = deque(maxlen=self.parameters.momentum_length)
        self._vidya_raw_window: deque[float] = deque(maxlen=self.parameters.smoothing_length)
        self._atr_seed: list[float] = []
        self._index = -1
        self._previous_candle: Candle | None = None
        self._previous_vidya_raw: float | None = None
        self._previous_atr: float | None = None
        self._previous_upper: float | None = None
        self._previous_lower: float | None = None
        self._trend = (
            TrendState.DOWN if semantics is StrategySemantics.PINE_V6 else TrendState.UNINITIALIZED
        )

    @property
    def processed_bars(self) -> int:
        return self._index + 1

    def update(self, candle: Candle) -> IndicatorPoint:
        self._validate_candle(candle)
        self._index += 1
        index = self._index

        if self._previous_candle is None:
            momentum = 0.0
            positive = 0.0
            negative = 0.0
        else:
            momentum = candle.close - self._previous_candle.close
            positive = max(momentum, 0.0)
            negative = max(-momentum, 0.0)

        self._positive.append(positive)
        self._negative.append(negative)
        abs_cmo: float | None
        if (
            self.semantics is StrategySemantics.PINE_V6
            and len(self._positive) < self.parameters.momentum_length
        ):
            abs_cmo = None
        else:
            pos_sum = sum(self._positive)
            neg_sum = sum(self._negative)
            denominator = pos_sum + neg_sum
            abs_cmo = 0.0 if denominator == 0.0 else abs((pos_sum - neg_sum) / denominator)

        alpha = 2.0 / (self.parameters.vidya_length + 1.0)
        effective_alpha = alpha * abs_cmo if abs_cmo is not None else None
        vidya_raw: float | None
        if self._previous_vidya_raw is None:
            vidya_raw = candle.close
        elif effective_alpha is None:
            vidya_raw = None
        else:
            vidya_raw = (
                effective_alpha * candle.close + (1.0 - effective_alpha) * self._previous_vidya_raw
            )
        if vidya_raw is not None:
            self._vidya_raw_window.append(vidya_raw)
        vidya = (
            sum(self._vidya_raw_window) / self.parameters.smoothing_length
            if len(self._vidya_raw_window) == self.parameters.smoothing_length
            else None
        )

        if self._previous_candle is None:
            true_range = candle.high - candle.low
        else:
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - self._previous_candle.close),
                abs(candle.low - self._previous_candle.close),
            )

        atr: float | None = None
        if index < self.parameters.atr_length:
            self._atr_seed.append(true_range)
        if index == self.parameters.atr_length - 1:
            atr = sum(self._atr_seed) / self.parameters.atr_length
        elif index >= self.parameters.atr_length:
            if self._previous_atr is None:
                raise RuntimeError("ATR state was not initialized")
            atr = (
                self._previous_atr * (self.parameters.atr_length - 1) + true_range
            ) / self.parameters.atr_length

        upper = (
            vidya + atr * self.parameters.band_multiplier
            if vidya is not None and atr is not None
            else None
        )
        lower = (
            vidya - atr * self.parameters.band_multiplier
            if vidya is not None and atr is not None
            else None
        )

        flip_up = False
        flip_down = False
        if self.semantics is StrategySemantics.DMS_V1:
            if index == self.parameters.warmup_bars - 1:
                self._trend = TrendState.DOWN
            elif index >= self.parameters.warmup_bars:
                if (
                    upper is None
                    or lower is None
                    or self._previous_upper is None
                    or self._previous_lower is None
                    or self._previous_candle is None
                ):
                    raise StrategyInputError("bands are invalid after warm-up")
                flip_up = (
                    candle.close > upper and self._previous_candle.close <= self._previous_upper
                )
                flip_down = (
                    candle.close < lower and self._previous_candle.close >= self._previous_lower
                )
                if flip_up:
                    self._trend = TrendState.UP
                elif flip_down:
                    self._trend = TrendState.DOWN
        elif (
            upper is not None
            and lower is not None
            and self._previous_upper is not None
            and self._previous_lower is not None
            and self._previous_candle is not None
        ):
            previous_trend = self._trend
            cross_up = candle.close > upper and self._previous_candle.close <= self._previous_upper
            cross_down = (
                candle.close < lower and self._previous_candle.close >= self._previous_lower
            )
            if cross_up:
                self._trend = TrendState.UP
            if cross_down:
                self._trend = TrendState.DOWN
            flip_up = previous_trend is TrendState.DOWN and self._trend is TrendState.UP
            flip_down = previous_trend is TrendState.UP and self._trend is TrendState.DOWN

        breakout: float | None = None
        ranked: float | None = None
        if flip_up and atr is not None and upper is not None:
            if atr <= 0.0:
                raise StrategyInputError("ATR must be positive for breakout ranking")
            breakout = (candle.close - upper) / atr
            if breakout > 0.0:
                ranked = rank_strength(breakout)

        point = IndicatorPoint(
            symbol=self.symbol,
            strategy_version=self.strategy_version,
            index=index,
            candle=candle,
            abs_cmo=abs_cmo,
            vidya_raw=vidya_raw,
            vidya=vidya,
            true_range=true_range,
            atr=atr,
            upper=upper,
            lower=lower,
            trend=self._trend,
            flip_up=flip_up,
            flip_down=flip_down,
            breakout_strength=breakout,
            rank_strength=ranked,
            tradable=index >= self.parameters.warmup_bars,
        )

        self._previous_candle = candle
        self._previous_vidya_raw = vidya_raw
        if atr is not None:
            self._previous_atr = atr
        self._previous_upper = upper
        self._previous_lower = lower
        return point

    def evaluate(self, candles: Iterable[Candle]) -> list[IndicatorPoint]:
        return [self.update(candle) for candle in candles]

    @staticmethod
    def signal_for(point: IndicatorPoint, is_long: bool) -> Signal | None:
        if not point.tradable or point.atr is None or point.upper is None or point.lower is None:
            return None
        action: SignalAction | None = None
        if point.flip_up and not is_long:
            action = SignalAction.ENTER_LONG
        elif point.flip_down and is_long:
            action = SignalAction.EXIT_LONG
        if action is None:
            return None
        return Signal(
            signal_id=_signal_id(point, action),
            symbol=point.symbol,
            action=action,
            candle_close_time_utc=point.candle.close_time_utc,
            strategy_version=point.strategy_version,
            point_index=point.index,
            close=point.candle.close,
            upper=point.upper,
            lower=point.lower,
            atr=point.atr,
            breakout_strength=point.breakout_strength,
        )

    def _validate_candle(self, candle: Candle) -> None:
        if candle.symbol != self.symbol:
            raise StrategyInputError(
                f"strategy for {self.symbol} cannot process candle for {candle.symbol}"
            )
        if not candle.closed:
            raise StrategyInputError("provisional candle cannot be strategy input")
        if not candle.ohlc_is_valid:
            raise StrategyInputError("invalid OHLCV candle")
        if self._previous_candle is not None:
            expected = self._previous_candle.open_time_utc + self.expected_interval
            if candle.open_time_utc != expected:
                raise StrategyInputError(
                    f"non-contiguous candle sequence: expected {expected.isoformat()}, "
                    f"got {candle.open_time_utc.isoformat()}"
                )


def evaluate_batch(
    symbol: str,
    candles: Iterable[Candle],
    parameters: StrategyParameters | None = None,
    semantics: StrategySemantics = StrategySemantics.DMS_V1,
    strategy_version: str | None = None,
) -> list[IndicatorPoint]:
    """Convenience wrapper that always starts from a clean strategy state."""

    return HixtonStrategy(
        symbol=symbol,
        parameters=parameters,
        semantics=semantics,
        strategy_version=strategy_version,
    ).evaluate(candles)

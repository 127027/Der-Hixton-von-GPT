"""Shared Hixton policy decisions for explicit V5 research and V6 Paper profiles."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from math import isfinite

from hixton.domain.models import IndicatorPoint, Signal, SignalAction
from hixton.domain.strategy import HixtonStrategy


@dataclass(frozen=True, slots=True)
class TradePolicy:
    cmo_floor: float = 0.0
    slope_bars: int = 0
    stop_atr: float = 0.0
    trail_atr: float = 0.0

    def __post_init__(self) -> None:
        if not all(isfinite(v) and v >= 0 for v in (self.cmo_floor, self.stop_atr, self.trail_atr)):
            raise ValueError("policy values must be finite and non-negative")
        if (
            self.cmo_floor > 1
            or type(self.slope_bars) is not int
            or self.slope_bars not in (0, 24, 72)
        ):
            raise ValueError("invalid CMO threshold or slope lookback")


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    signal: Signal | None
    block_reason: str | None = None
    exit_reason: str | None = None


class TradePolicyGate:
    def __init__(self, policy: TradePolicy | None = None) -> None:
        self.policy = policy or TradePolicy()
        self._vidya: deque[float | None] = deque(maxlen=self.policy.slope_bars + 1)

    def decide(
        self,
        point: IndicatorPoint,
        *,
        entry_price: float | None = None,
        entry_atr: float = 0.0,
        highest_close: float = 0.0,
    ) -> PolicyDecision:
        """Called once per closed bar, including warm-up. Stops trigger at CLOSE only."""
        self._vidya.append(point.vidya)
        signal = HixtonStrategy.signal_for(point, is_long=entry_price is not None)
        if signal is not None and signal.action is SignalAction.ENTER_LONG:
            if (point.abs_cmo or 0.0) < self.policy.cmo_floor:
                return PolicyDecision(signal, block_reason="POLICY_CMO")
            if self.policy.slope_bars and (
                len(self._vidya) <= self.policy.slope_bars
                or self._vidya[0] is None
                or point.vidya is None
                or point.vidya <= self._vidya[0]
            ):
                return PolicyDecision(signal, block_reason="POLICY_VIDYA_SLOPE")
        if signal is not None:
            return PolicyDecision(signal)
        if entry_price is None or not point.tradable or entry_atr <= 0:
            return PolicyDecision(None)
        reason = None
        if (
            self.policy.stop_atr
            and point.candle.close <= entry_price - self.policy.stop_atr * entry_atr
        ):
            reason = "POLICY_STOP_ATR"
        elif (
            self.policy.trail_atr
            and point.candle.close <= highest_close - self.policy.trail_atr * entry_atr
        ):
            reason = "POLICY_TRAIL_ATR"
        if reason is None:
            return PolicyDecision(None)
        # Do not mutate the indicator trend or synthesize a new BUY after a stop.
        signal = HixtonStrategy.signal_for(
            replace(point, flip_down=True, flip_up=False), is_long=True
        )
        return PolicyDecision(signal, exit_reason=reason)

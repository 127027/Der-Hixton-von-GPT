"""Five bounded gap fillers sharing the unchanged ten-Core strategy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime

from hixton.domain.models import (
    IndicatorPoint,
    Signal,
    SignalAction,
    StrategyParameters,
    StrategySemantics,
    TrendState,
)
from hixton.domain.trade_policy import TradePolicy

CORE_SYMBOLS: tuple[str, ...] = (
    "BTCUSDC",
    "ETHUSDC",
    "BNBUSDC",
    "SOLUSDC",
    "XRPUSDC",
    "ADAUSDC",
    "LINKUSDC",
    "AVAXUSDC",
    "DOTUSDC",
    "DOGEUSDC",
)
SATELLITE_SYMBOLS: tuple[str, ...] = (
    "SUIUSDC",
    "NEARUSDC",
    "UNIUSDC",
    "AAVEUSDC",
    "BCHUSDC",
)
ALL_15_SYMBOLS: tuple[str, ...] = CORE_SYMBOLS + SATELLITE_SYMBOLS
# Core keeps its original ranked-repeat allocation. All five fillers only
# enter fully idle periods and yield completely to eligible Core entries.
ACTIVE_SHARED_SATELLITES: tuple[str, ...] = SATELLITE_SYMBOLS
FILLER_ROUTING_VERSION = "FILLER-V3-STRICT-CORE-PRIORITY"


@dataclass(frozen=True, slots=True)
class SatelliteProfile:
    symbol: str
    history_proxy: str
    parameters: StrategyParameters
    trade_policy: TradePolicy
    semantics: StrategySemantics = StrategySemantics.DMS_V1
    horizon_hours: int = 0
    min_atr_pct: float = 0.0
    max_atr_pct: float = 1.0
    min_trend_atr: float = -999.0
    max_trend_atr: float = 999.0
    min_breakout_atr: float = 0.0
    max_breakout_atr: float = 999.0
    min_abs_cmo: float = 0.0
    reentry_atr_level: float | None = None
    entry_interval_hours: int = 0

    def __post_init__(self) -> None:
        if (
            type(self.entry_interval_hours) is not int
            or self.entry_interval_hours < 0
            or (self.entry_interval_hours and 24 % self.entry_interval_hours)
            or type(self.horizon_hours) is not int
            or self.horizon_hours < 0
        ):
            raise ValueError("invalid Satellite entry interval or holding horizon")

    def entry_block_reason(self, point: IndicatorPoint) -> str | None:
        if point.atr is None or point.vidya is None or point.candle.close <= 0 or point.atr <= 0:
            return "SATELLITE_REGIME_INPUT_UNAVAILABLE"
        atr_pct = point.atr / point.candle.close
        trend_atr = (point.candle.close - point.vidya) / point.atr
        breakout = point.breakout_strength or 0.0
        abs_cmo = point.abs_cmo or 0.0
        if atr_pct < self.min_atr_pct:
            return "SATELLITE_ATR_TOO_LOW"
        if atr_pct > self.max_atr_pct:
            return "SATELLITE_ATR_TOO_HIGH"
        if trend_atr < self.min_trend_atr:
            return "SATELLITE_TREND_TOO_WEAK"
        if trend_atr > self.max_trend_atr:
            return "SATELLITE_TREND_TOO_EXTENDED"
        if breakout < self.min_breakout_atr:
            return "SATELLITE_BREAKOUT_TOO_WEAK"
        if breakout > self.max_breakout_atr:
            return "SATELLITE_BREAKOUT_TOO_HIGH"
        if abs_cmo < self.min_abs_cmo:
            return "SATELLITE_CMO_TOO_WEAK"
        return None


SATELLITE_PROFILES: tuple[SatelliteProfile, ...] = (
    SatelliteProfile(
        "SUIUSDC",
        "SUIUSDT",
        StrategyParameters(
            vidya_length=15,
            momentum_length=20,
            smoothing_length=14,
            atr_length=120,
            band_multiplier=2.3,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.4, slope_bars=0, stop_atr=2.5, trail_atr=0),
        horizon_hours=0,
        entry_interval_hours=12,
        max_atr_pct=0.0175,
    ),
    SatelliteProfile(
        "NEARUSDC",
        "NEARUSDT",
        StrategyParameters(
            vidya_length=10,
            momentum_length=20,
            smoothing_length=15,
            atr_length=200,
            band_multiplier=2.8,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=0, stop_atr=0, trail_atr=0),
        horizon_hours=48,
        entry_interval_hours=12,
    ),
    SatelliteProfile(
        "UNIUSDC",
        "UNIUSDT",
        StrategyParameters(
            vidya_length=12,
            momentum_length=20,
            smoothing_length=10,
            atr_length=120,
            band_multiplier=2.0,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.3, slope_bars=72, stop_atr=0, trail_atr=0),
        horizon_hours=0,
        entry_interval_hours=12,
        min_abs_cmo=0.15,
        reentry_atr_level=0.50,
    ),
    SatelliteProfile(
        "AAVEUSDC",
        "AAVEUSDT",
        StrategyParameters(
            vidya_length=10,
            momentum_length=12,
            smoothing_length=15,
            atr_length=200,
            band_multiplier=2.0,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.3, slope_bars=0, stop_atr=2.0, trail_atr=0),
        horizon_hours=120,
        entry_interval_hours=12,
        min_atr_pct=0.005,
        max_atr_pct=0.025,
        min_trend_atr=0.5,
        max_trend_atr=2.5,
    ),
    SatelliteProfile(
        "BCHUSDC",
        "BCHUSDT",
        StrategyParameters(
            vidya_length=13,
            momentum_length=16,
            smoothing_length=15,
            atr_length=200,
            band_multiplier=3.2,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=0, stop_atr=0, trail_atr=0),
        horizon_hours=0,
        entry_interval_hours=12,
        max_atr_pct=0.020,
    ),
)

SATELLITE_PROFILE_BY_SYMBOL = {profile.symbol: profile for profile in SATELLITE_PROFILES}


def satellite_entry_point(point: IndicatorPoint) -> IndicatorPoint:
    """Allow bounded continuation entries using only this finalized hourly bar.

    This changes the policy input, never the indicator state. Exchange, risk,
    momentum, slope and regime gates still apply. Core points are untouched.
    """
    profile = SATELLITE_PROFILE_BY_SYMBOL.get(point.symbol)
    if (
        profile is None
        or not point.strategy_version.startswith("HIXTON-V8-")
        or not point.candle.closed
        or not point.tradable
        or point.trend is not TrendState.UP
        or point.flip_down
        or not profile.entry_interval_hours
        or (point.candle.open_time_utc.hour + 1) % profile.entry_interval_hours
    ):
        return point
    return replace(point, flip_up=True, flip_down=False)


def shared_satellite_entry_block_reason(
    symbol: str,
    point: IndicatorPoint,
) -> str | None:
    """Return the point-in-time entry regime gate for an active filler."""

    profile = SATELLITE_PROFILE_BY_SYMBOL.get(symbol.replace("/", "").upper())
    if profile is None or profile.symbol not in ACTIVE_SHARED_SATELLITES:
        return "SATELLITE_RESEARCH_ONLY"
    return profile.entry_block_reason(point)


def satellite_handoff_symbols(
    *,
    core_entry_count: int,
    position_slots: dict[str, int],
    active_satellites: frozenset[str],
    slot_count: int,
    exiting_symbols: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """All fillers yield at an eligible Core entry, including its second tranche.

    Planned exits are already handled by the caller. No Core opportunity means
    no forced sale. The same routing is used by Backtest, Paper and Live.
    """
    if core_entry_count <= 0:
        return ()
    return tuple(sorted(set(position_slots) & active_satellites - exiting_symbols))



def shared_satellite_horizon_exit(
    symbol: str,
    point: IndicatorPoint,
    *,
    entry_time_utc: datetime,
) -> Signal | None:
    """Evaluate the per-profile holding bound using only a finalized closed bar."""

    normalized = symbol.replace("/", "").upper()
    profile = SATELLITE_PROFILE_BY_SYMBOL.get(normalized)
    if (
        profile is None
        or not point.candle.closed
        or normalized not in ACTIVE_SHARED_SATELLITES
        or profile.horizon_hours <= 0
    ):
        return None
    age_hours = (point.candle.close_time_utc - entry_time_utc).total_seconds() / 3600
    if age_hours < profile.horizon_hours:
        return None
    upper = point.upper if point.upper is not None else point.candle.close
    lower = point.lower if point.lower is not None else point.candle.close
    atr = point.atr if point.atr is not None else 0.0
    digest = hashlib.sha256(
        (
            f"SATELLITE_MAX_HOLD|{normalized}|{entry_time_utc.isoformat()}|"
            f"{point.candle.close_time_utc.isoformat()}|{profile.horizon_hours}"
        ).encode()
    ).hexdigest()
    return Signal(
        signal_id=digest,
        symbol=normalized,
        action=SignalAction.EXIT_LONG,
        candle_close_time_utc=point.candle.close_time_utc,
        strategy_version=point.strategy_version,
        point_index=point.index,
        close=point.candle.close,
        upper=float(upper),
        lower=float(lower),
        atr=float(atr),
        breakout_strength=point.breakout_strength,
    )


# Release audit trigger v8: exact-head integration and swarm verification share this source.

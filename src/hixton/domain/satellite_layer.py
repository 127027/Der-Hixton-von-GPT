"""Validated five-Satellite layer for the 15-market Hixton candidate.

These profiles are copied from the accepted isolated 5x250 research references.
They are intentionally separate from the ten protected Core profiles.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from hixton.domain.models import (
    IndicatorPoint,
    Signal,
    SignalAction,
    StrategyParameters,
    StrategySemantics,
)
from hixton.domain.trade_policy import TradePolicy

CORE_SYMBOLS: tuple[str, ...] = (
    "BTCUSDC","ETHUSDC","BNBUSDC","SOLUSDC","XRPUSDC",
    "ADAUSDC","LINKUSDC","AVAXUSDC","DOTUSDC","DOGEUSDC",
)
SATELLITE_SYMBOLS: tuple[str, ...] = (
    "SUIUSDC","NEARUSDC","UNIUSDC","AAVEUSDC","BCHUSDC",
)
ALL_15_SYMBOLS: tuple[str, ...] = CORE_SYMBOLS + SATELLITE_SYMBOLS
# Shared-portfolio activation is deliberately narrower than the research
# universe. All five remain available for isolated 15x250 evidence; only
# Satellites that add stressed shared-PnL without harming the Core are active
# gap fillers. Current validated shared winner: NEAR + BCH. Capital sizing is
# derived from the shared capital plan.
ACTIVE_SHARED_SATELLITES: tuple[str, ...] = ("NEARUSDC", "BCHUSDC")


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
        "SUIUSDC", "SUIUSDT",
        StrategyParameters(
            vidya_length=15,
            momentum_length=20,
            smoothing_length=14,
            atr_length=120,
            band_multiplier=2.3,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.4,slope_bars=0,stop_atr=2.5,trail_atr=0),
        max_atr_pct=0.0175,
    ),
    SatelliteProfile(
        "NEARUSDC", "NEARUSDT",
        StrategyParameters(
            vidya_length=10,
            momentum_length=20,
            smoothing_length=15,
            atr_length=200,
            band_multiplier=2.8,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0,slope_bars=0,stop_atr=0,trail_atr=0),
        horizon_hours=48,
    ),
    SatelliteProfile(
        "UNIUSDC", "UNIUSDT",
        StrategyParameters(
            vidya_length=12,
            momentum_length=20,
            smoothing_length=10,
            atr_length=120,
            band_multiplier=2.0,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.3,slope_bars=72,stop_atr=0,trail_atr=0),
        min_abs_cmo=0.15,
        reentry_atr_level=0.50,
    ),
    SatelliteProfile(
        "AAVEUSDC", "AAVEUSDT",
        StrategyParameters(
            vidya_length=10,
            momentum_length=12,
            smoothing_length=15,
            atr_length=200,
            band_multiplier=2.0,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.3,slope_bars=0,stop_atr=2.0,trail_atr=0),
        horizon_hours=120,
        min_atr_pct=0.005,
        max_atr_pct=0.025,
        min_trend_atr=0.5,
        max_trend_atr=2.5,
    ),
    SatelliteProfile(
        "BCHUSDC", "BCHUSDT",
        StrategyParameters(
            vidya_length=13,
            momentum_length=16,
            smoothing_length=15,
            atr_length=200,
            band_multiplier=3.2,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0,slope_bars=0,stop_atr=0,trail_atr=0),
        max_atr_pct=0.020,
    ),
)

SATELLITE_PROFILE_BY_SYMBOL = {profile.symbol: profile for profile in SATELLITE_PROFILES}

def shared_satellite_entry_block_reason(
    symbol: str,
    point: IndicatorPoint,
) -> str | None:
    """Return the frozen shared-gap entry gate for one active Satellite."""

    profile = SATELLITE_PROFILE_BY_SYMBOL.get(symbol.replace("/", "").upper())
    if profile is None or profile.symbol not in ACTIVE_SHARED_SATELLITES:
        return "SATELLITE_RESEARCH_ONLY"
    return profile.entry_block_reason(point)


def shared_satellite_horizon_exit(
    symbol: str,
    point: IndicatorPoint,
    *,
    entry_time_utc: datetime,
) -> Signal | None:
    """Create the tested next-open max-hold exit for an active filler.

    The accepted NEAR profile uses a 48-hour filler horizon. In the research
    router the remaining-value score is guaranteed <= 0.50 once age reaches
    that horizon, so the product-equivalent rule is a deterministic 48-hour
    max hold evaluated only on a fully closed bar.
    """

    normalized = symbol.replace("/", "").upper()
    profile = SATELLITE_PROFILE_BY_SYMBOL.get(normalized)
    if (
        profile is None
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

# Release audit trigger v6: exact-head integration and swarm verification share this source.

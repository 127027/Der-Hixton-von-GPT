"""Validated five-Satellite layer for the 15-market Hixton candidate.

These profiles are copied from the accepted isolated 5x250 research references.
They are intentionally separate from the ten protected Core profiles.
"""

from __future__ import annotations

from dataclasses import dataclass

from hixton.domain.models import IndicatorPoint, StrategyParameters, StrategySemantics
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
# gap fillers. Current validated shared winner: NEAR + BCH.
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

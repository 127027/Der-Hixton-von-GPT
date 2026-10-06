"""Explicit immutable strategy definitions; runtime activation is intentionally separate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from hixton.constants import (
    HIXTON_SPEC_VERSION,
    HIXTON_V2_RESEARCH_VERSION,
    HIXTON_V3_SLOT_VERSION,
    TIMEFRAME,
)
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.markets import symbols_for_quote
from hixton.domain.models import StrategyParameters, StrategySemantics
from hixton.domain.satellite_layer import (
    ACTIVE_SHARED_SATELLITES,
    SATELLITE_PROFILES,
    SATELLITE_SYMBOLS,
)
from hixton.domain.trade_policy import TradePolicy


@dataclass(frozen=True, slots=True)
class CoinProfile:
    symbol: str
    parameters: StrategyParameters
    trade_policy: TradePolicy


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    key: str
    backtest_version: str
    version: str
    reference: str
    semantics: StrategySemantics
    parameters: StrategyParameters
    paper_approved: bool
    slot_allocation: str
    coin_profiles: tuple[CoinProfile, ...] = ()
    quote_asset: str = "USDC"
    satellite_symbols: tuple[str, ...] = ()
    active_shared_satellites: tuple[str, ...] = ()
    satellite_semantics: StrategySemantics | None = None

    @property
    def symbols(self) -> tuple[str, ...]:
        if self.coin_profiles:
            return tuple(profile.symbol for profile in self.coin_profiles)
        return symbols_for_quote(self.quote_asset)

    def __post_init__(self) -> None:
        profile_symbols = tuple(profile.symbol for profile in self.coin_profiles)
        if self.key == "v6" and profile_symbols != symbols_for_quote(self.quote_asset):
            raise ValueError("coin profiles require all ten symbols in DMS order")
        if len(set(profile_symbols)) != len(profile_symbols):
            raise ValueError("coin profiles must use unique symbols")
        if any(not symbol.endswith(self.quote_asset) for symbol in profile_symbols):
            raise ValueError("coin profile quote asset mismatch")
        if self.satellite_symbols and not set(self.satellite_symbols).issubset(profile_symbols):
            raise ValueError("satellite symbols must be present in coin profiles")
        if self.satellite_symbols and self.satellite_semantics is None:
            raise ValueError("satellite semantics are required for a mixed strategy")
        if not set(self.active_shared_satellites).issubset(set(self.satellite_symbols)):
            raise ValueError("active shared Satellites must be a subset of Satellite symbols")
        if any(p.parameters.warmup_bars != self.parameters.warmup_bars for p in self.coin_profiles):
            raise ValueError("coin profiles require a shared warmup length")

    def semantics_for(self, symbol: str) -> StrategySemantics:
        normalized = symbol.replace("/", "").upper()
        if normalized not in self.symbols:
            raise ValueError(f"unsupported symbol: {symbol}")
        if normalized in self.satellite_symbols:
            assert self.satellite_semantics is not None
            return self.satellite_semantics
        return self.semantics

    def parameters_for(self, symbol: str) -> StrategyParameters:
        normalized = symbol.replace("/", "").upper()
        if normalized not in self.symbols:
            raise ValueError(f"unsupported symbol: {symbol}")
        return next(
            (p.parameters for p in self.coin_profiles if p.symbol == normalized), self.parameters
        )

    def policy_for(self, symbol: str) -> TradePolicy:
        self.parameters_for(symbol)
        normalized = symbol.replace("/", "").upper()
        return next(
            (p.trade_policy for p in self.coin_profiles if p.symbol == normalized), TradePolicy()
        )

    def parameter_map(self) -> dict[str, StrategyParameters] | None:
        return {p.symbol: p.parameters for p in self.coin_profiles} if self.coin_profiles else None

    def policy_map(self) -> dict[str, TradePolicy] | None:
        return (
            {p.symbol: p.trade_policy for p in self.coin_profiles} if self.coin_profiles else None
        )

    def profiles_payload(self) -> dict[str, object]:
        return {
            p.symbol: {"parameters": asdict(p.parameters), "trade_policy": asdict(p.trade_policy)}
            for p in self.coin_profiles
        }

    def config_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "key": self.key,
            "version": self.version,
            "timeframe": TIMEFRAME,
            "source": "close",
            "slot_allocation": self.slot_allocation,
            "long_only": True,
            "compounding": False,
        }
        if self.coin_profiles:
            payload["profiles"] = self.profiles_payload()
        else:
            payload.update(asdict(self.parameters))
        payload["quote_asset"] = self.quote_asset
        if self.satellite_symbols:
            payload["satellite_symbols"] = list(self.satellite_symbols)
            payload["active_shared_satellites"] = list(self.active_shared_satellites)
        return payload


V1_STRATEGY = StrategyDefinition(
    key="v1",
    backtest_version="v1",
    version=HIXTON_SPEC_VERSION,
    reference="DMS/03_STRATEGIE_HIXTON.md",
    semantics=StrategySemantics.DMS_V1,
    parameters=StrategyParameters(),
    paper_approved=False,
    slot_allocation=ONE_PER_SYMBOL,
)

V2_RESEARCH_STRATEGY = StrategyDefinition(
    key="v2",
    backtest_version="v2",
    version=HIXTON_V2_RESEARCH_VERSION,
    reference="strategy/pine/Der_Hixton_Indikator_v6.pine",
    semantics=StrategySemantics.PINE_V6,
    parameters=StrategyParameters(
        vidya_length=6,
        momentum_length=20,
        smoothing_length=8,
        atr_length=60,
        band_multiplier=3.8,
        warmup_bars=400,
    ),
    paper_approved=True,
    slot_allocation=ONE_PER_SYMBOL,
)

V3_SLOT_STRATEGY = StrategyDefinition(
    key="v3",
    backtest_version="v3",
    version=HIXTON_V3_SLOT_VERSION,
    reference="DMS/03_STRATEGIE_HIXTON.md",
    semantics=StrategySemantics.PINE_V6,
    parameters=V2_RESEARCH_STRATEGY.parameters,
    paper_approved=False,
    slot_allocation=RANKED_REPEAT,
)

_V6_PROFILES = (
    CoinProfile(
        "BTCUSDC",
        StrategyParameters(
            vidya_length=5,
            momentum_length=20,
            smoothing_length=8,
            atr_length=120,
            band_multiplier=4.4,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.2, slope_bars=0, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "ETHUSDC",
        StrategyParameters(
            vidya_length=6,
            momentum_length=20,
            smoothing_length=8,
            atr_length=60,
            band_multiplier=3.8,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=24, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "BNBUSDC",
        StrategyParameters(
            vidya_length=10,
            momentum_length=20,
            smoothing_length=8,
            atr_length=120,
            band_multiplier=5.0,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=0, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "SOLUSDC",
        StrategyParameters(
            vidya_length=6,
            momentum_length=20,
            smoothing_length=15,
            atr_length=60,
            band_multiplier=3.8,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=0, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "XRPUSDC",
        StrategyParameters(
            vidya_length=6,
            momentum_length=20,
            smoothing_length=8,
            atr_length=120,
            band_multiplier=3.2,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.15, slope_bars=0, stop_atr=4, trail_atr=0),
    ),
    CoinProfile(
        "ADAUSDC",
        StrategyParameters(
            vidya_length=8,
            momentum_length=20,
            smoothing_length=8,
            atr_length=60,
            band_multiplier=4.4,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=0, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "LINKUSDC",
        StrategyParameters(
            vidya_length=6,
            momentum_length=20,
            smoothing_length=8,
            atr_length=60,
            band_multiplier=3.8,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=24, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "AVAXUSDC",
        StrategyParameters(
            vidya_length=6,
            momentum_length=20,
            smoothing_length=8,
            atr_length=90,
            band_multiplier=5.5,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0, slope_bars=0, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "DOTUSDC",
        StrategyParameters(
            vidya_length=6,
            momentum_length=20,
            smoothing_length=8,
            atr_length=120,
            band_multiplier=3.8,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.35, slope_bars=0, stop_atr=0, trail_atr=0),
    ),
    CoinProfile(
        "DOGEUSDC",
        StrategyParameters(
            vidya_length=6,
            momentum_length=16,
            smoothing_length=14,
            atr_length=120,
            band_multiplier=4.3,
            warmup_bars=400,
        ),
        TradePolicy(cmo_floor=0.2, slope_bars=0, stop_atr=0, trail_atr=0),
    ),
)
_V6_DIGEST = hashlib.sha256(
    json.dumps([asdict(p) for p in _V6_PROFILES], sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
V6_COIN_STRATEGY = StrategyDefinition(
    key="v6",
    backtest_version="v6",
    version=f"HIXTON-V6-COIN-PAPER-1-{_V6_DIGEST[:12]}",
    reference="strategy/pine/Der_Hixton_Indikator_v6.pine",
    semantics=StrategySemantics.PINE_V6,
    parameters=V2_RESEARCH_STRATEGY.parameters,
    # Frozen ten-coin Core incumbent. Keep this definition byte-for-byte
    # equivalent in behavior so V6 remains the regression anchor.
    paper_approved=True,
    slot_allocation=RANKED_REPEAT,
    coin_profiles=_V6_PROFILES,
)

_V8_PROFILES = _V6_PROFILES + tuple(
    CoinProfile(profile.symbol, profile.parameters, profile.trade_policy)
    for profile in SATELLITE_PROFILES
)
_V8_DIGEST = hashlib.sha256(
    json.dumps([asdict(p) for p in _V8_PROFILES], sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
V8_SATELLITE_STRATEGY = StrategyDefinition(
    key="v8",
    backtest_version="v8",
    version=f"HIXTON-V8-CORE10-SAT2-PAPER-1-{_V8_DIGEST[:12]}",
    reference="strategy/pine/Der_Hixton_Indikator_v6.pine",
    semantics=StrategySemantics.PINE_V6,
    parameters=V2_RESEARCH_STRATEGY.parameters,
    paper_approved=True,
    slot_allocation=RANKED_REPEAT,
    coin_profiles=_V8_PROFILES,
    satellite_symbols=SATELLITE_SYMBOLS,
    active_shared_satellites=ACTIVE_SHARED_SATELLITES,
    satellite_semantics=StrategySemantics.DMS_V1,
)

V7_USDC_STRATEGY = StrategyDefinition(
    key="v7",
    backtest_version="v7",
    version=f"HIXTON-V7-USDC-VALIDATION-1-{_V6_DIGEST[:12]}",
    reference=V6_COIN_STRATEGY.reference,
    semantics=V6_COIN_STRATEGY.semantics,
    parameters=V6_COIN_STRATEGY.parameters,
    paper_approved=False,  # Validate USDC data/results before any runtime/account migration.
    slot_allocation=ONE_PER_SYMBOL,
    coin_profiles=tuple(
        CoinProfile(p.symbol.removesuffix("USDC") + "USDC", p.parameters, p.trade_policy)
        for p in _V6_PROFILES
    ),
    quote_asset="USDC",
)


STRATEGY_DEFINITIONS = {
    V1_STRATEGY.key: V1_STRATEGY,
    V2_RESEARCH_STRATEGY.key: V2_RESEARCH_STRATEGY,
    V3_SLOT_STRATEGY.key: V3_SLOT_STRATEGY,
    V6_COIN_STRATEGY.key: V6_COIN_STRATEGY,
    V7_USDC_STRATEGY.key: V7_USDC_STRATEGY,
    V8_SATELLITE_STRATEGY.key: V8_SATELLITE_STRATEGY,
}


def strategy_definition(key: str) -> StrategyDefinition:
    try:
        return STRATEGY_DEFINITIONS[key.lower()]
    except KeyError as error:
        raise ValueError(f"unsupported strategy version: {key}") from error

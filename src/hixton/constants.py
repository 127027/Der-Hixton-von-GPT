"""Project-wide constants fixed by the active Hixton specification."""

from __future__ import annotations

from datetime import timedelta

HIXTON_SPEC_VERSION = "HIXTON-SPEC-1.0"
HIXTON_V2_RESEARCH_VERSION = "HIXTON-V2-RESEARCH-CANDIDATE-1"
HIXTON_V3_SLOT_VERSION = "HIXTON-V3-SLOT-CANDIDATE-1"
STRATEGY_ID = "hixton_vidya_atr"
EXCHANGE = "binance_spot"
TIMEFRAME = "1h"
TIMEFRAME_DELTA = timedelta(hours=1)
QUOTE_ASSET = "USDC"
BASE_ASSETS: tuple[str, ...] = (
    "BTC",
    "ETH",
    "BNB",
    "SOL",
    "XRP",
    "ADA",
    "LINK",
    "AVAX",
    "DOT",
    "DOGE",
)
SYMBOLS: tuple[str, ...] = tuple(base + QUOTE_ASSET for base in BASE_ASSETS)
SYMBOL_TIE_BREAK: dict[str, int] = {symbol: rank for rank, symbol in enumerate(SYMBOLS)}

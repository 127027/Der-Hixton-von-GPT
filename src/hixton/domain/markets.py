"""Canonical market identity for active runtime and isolated research replays."""

from __future__ import annotations

from hixton.constants import BASE_ASSETS, QUOTE_ASSET, SYMBOLS

_RESEARCH_QUOTES = frozenset({"USDT", "USDC"})


def symbols_for_quote(quote_asset: str) -> tuple[str, ...]:
    """Return only the active runtime universe.

    Runtime configuration remains deliberately USDC-only. Historical quote
    comparisons must use :func:`research_symbols_for_quote` instead.
    """
    if quote_asset.upper() != QUOTE_ASSET:
        raise ValueError(f"Only {QUOTE_ASSET} is supported by the active runtime")
    return tuple(base + QUOTE_ASSET for base in BASE_ASSETS)


def research_symbols_for_quote(quote_asset: str) -> tuple[str, ...]:
    """Return the exact ten-market universe for a read-only research quote."""
    quote = quote_asset.upper()
    if quote not in _RESEARCH_QUOTES:
        raise ValueError("Research quote must be USDT or USDC")
    return tuple(base + quote for base in BASE_ASSETS)


def split_market(symbol: str) -> tuple[str, str]:
    """Strict asset identity, not a permissive suffix replacement."""
    for quote in ("USDT", "USDC"):
        if symbol in research_symbols_for_quote(quote):
            return symbol.removesuffix(quote), quote
    raise ValueError("Unsupported Hixton Spot market")


def validate_market_symbols(symbols: tuple[str, ...]) -> str:
    """Validate the active bot universe; never accepts legacy USDT."""
    if symbols != SYMBOLS:
        raise ValueError("Ten ordered USDC markets required")
    return QUOTE_ASSET


def validate_research_market_symbols(symbols: tuple[str, ...], quote_asset: str) -> str:
    """Validate an explicitly read-only USDT/USDC comparison universe.

    This is intentionally separate from ``validate_market_symbols`` so adding a
    historical comparison can never make USDT valid for Paper/runtime trading.
    """
    quote = quote_asset.upper()
    if symbols != research_symbols_for_quote(quote):
        raise ValueError(f"Ten ordered {quote} research markets required")
    return quote

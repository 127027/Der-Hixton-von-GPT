"""Shared exact-decimal Binance MARKET limits; no implicit order splitting.

Notional checks use the caller's reference/model price. Binance may evaluate a
different rolling average/reference price, which these OHLC simulations cannot
reconstruct. A local pass never overrides exchange validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_DOWN, Decimal
from math import lcm
from types import SimpleNamespace
from typing import Any, Protocol, cast

ZERO = Decimal(0)
FILTER_DECIMALS = (
    "tick_size",
    "step_size",
    "min_qty",
    "min_notional",
    "max_qty",
    "market_min_qty",
    "market_max_qty",
    "market_step_size",
    "max_notional",
)
MARKET_FILTER_FIELDS = (*FILTER_DECIMALS[4:], "notional_avg_price_mins", "market_limits_known")


class MarketRules(Protocol):
    @property
    def tick_size(self) -> Decimal: ...
    @property
    def step_size(self) -> Decimal: ...
    @property
    def min_qty(self) -> Decimal: ...
    @property
    def min_notional(self) -> Decimal: ...
    @property
    def max_qty(self) -> Decimal: ...
    @property
    def market_min_qty(self) -> Decimal: ...
    @property
    def market_max_qty(self) -> Decimal: ...
    @property
    def market_step_size(self) -> Decimal: ...
    @property
    def max_notional(self) -> Decimal: ...
    @property
    def notional_avg_price_mins(self) -> int: ...
    @property
    def market_limits_known(self) -> bool: ...


def validate_market_rules(rules: MarketRules) -> None:
    for name in FILTER_DECIMALS:
        value = getattr(rules, name)
        if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
            raise ValueError("Market filters require finite non-negative Decimal values")
    for lower, upper in (
        (rules.min_qty, rules.max_qty),
        (rules.market_min_qty, rules.market_max_qty),
        (rules.min_notional, rules.max_notional),
    ):
        if upper > ZERO and lower > upper:
            raise ValueError("Market filter minimum exceeds maximum")
    if type(rules.notional_avg_price_mins) is not int or rules.notional_avg_price_mins < 0:
        raise ValueError("Invalid market notional averaging window")
    if type(rules.market_limits_known) is not bool:
        raise ValueError("Invalid market filter provenance")


def market_quantity_step(rules: MarketRules) -> Decimal:
    """Both quantity grids apply; use their least common multiple, never max()."""
    steps = [value for value in (rules.step_size, rules.market_step_size) if value > ZERO]
    if not steps:
        return ZERO
    exponent = min(int(step.as_tuple().exponent) for step in steps)
    units = [int(step.scaleb(-exponent)) for step in steps]
    return Decimal(lcm(*units)).scaleb(exponent)


def round_market_quantity(quantity: Decimal, rules: MarketRules) -> Decimal:
    if not quantity.is_finite() or quantity < ZERO:
        raise ValueError("Market quantity must be finite and non-negative")
    step = market_quantity_step(rules)
    return (quantity / step).to_integral_value(rounding=ROUND_DOWN) * step if step else quantity


def market_order_block_reason(
    rules: MarketRules, quantity: Decimal, price: Decimal, *, quote: Decimal | None = None
) -> str | None:
    """Validate one MARKET order; maxima reject the order rather than cap/split it."""
    if not quantity.is_finite() or not price.is_finite() or price <= ZERO:
        return "INVALID_MARKET_AMOUNT"
    if quantity <= ZERO:
        return "MIN_QTY"
    notional = quantity * price if quote is None else quote
    if not notional.is_finite() or notional < ZERO:
        return "INVALID_MARKET_AMOUNT"
    if rules.max_qty > ZERO and quantity > rules.max_qty:
        return "LOT_SIZE_MAX_QTY"
    if rules.market_max_qty > ZERO and quantity > rules.market_max_qty:
        return "MARKET_LOT_SIZE_MAX_QTY"
    if rules.max_notional > ZERO and notional > rules.max_notional:
        return "NOTIONAL_MAX"
    if quantity < rules.min_qty:
        return "MIN_QTY"
    if quantity < rules.market_min_qty:
        return "MARKET_MIN_QTY"
    if notional < rules.min_notional:
        return "MIN_NOTIONAL"
    if any(
        step > ZERO and quantity % step != ZERO
        for step in (rules.step_size, rules.market_step_size)
    ):
        return "MARKET_QUANTITY_STEP"
    return None


def market_order_is_dust(reason: str | None) -> bool:
    return reason in {"MIN_QTY", "MARKET_MIN_QTY", "MIN_NOTIONAL"}


def market_filter_values(raw: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Parse effective MARKET filters; explicit false application flags are honored."""
    lot = raw.get("LOT_SIZE", {})
    market = raw.get("MARKET_LOT_SIZE", {})
    minimum = raw.get("MIN_NOTIONAL", {})
    notional = raw.get("NOTIONAL", {})

    def amount(item: Mapping[str, Any], name: str, *, required: bool = False) -> Decimal:
        if required and name not in item:
            raise ValueError("Active Binance market bound is missing")
        value = Decimal(str(item.get(name, "0")))
        if not value.is_finite() or value < ZERO:
            raise ValueError("Invalid finite Binance filter amount")
        return value

    def applies(item: Mapping[str, Any], name: str) -> bool:
        # Older cached fixtures omit flags. Preserve their conservative minimum;
        # fresh exchangeInfo explicit false always disables that market bound.
        value = item.get(name, True)
        if type(value) is not bool:
            raise ValueError("Invalid Binance market filter application flag")
        return value

    minimums = [ZERO]
    windows = [0]

    def window(item: Mapping[str, Any], *, required: bool = False) -> int:
        if required and "avgPriceMins" not in item:
            raise ValueError("Active Binance market averaging window is missing")
        value = item.get("avgPriceMins", 0)
        if type(value) is not int or value < 0:
            raise ValueError("Invalid Binance notional averaging window")
        return value

    if minimum and applies(minimum, "applyToMarket"):
        explicit = minimum.get("applyToMarket") is True
        minimums.append(amount(minimum, "minNotional", required=explicit))
        windows.append(window(minimum, required=explicit))
    if notional and applies(notional, "applyMinToMarket"):
        explicit = notional.get("applyMinToMarket") is True
        minimums.append(amount(notional, "minNotional", required=explicit))
        windows.append(window(notional, required=explicit))
    maximum = ZERO
    if notional and applies(notional, "applyMaxToMarket"):
        explicit = notional.get("applyMaxToMarket") is True
        maximum = amount(notional, "maxNotional", required=explicit)
        if explicit and maximum <= ZERO:
            raise ValueError("Active Binance market maximum must be positive")
        windows.append(window(notional, required=explicit))
    values = {
        "tick_size": amount(raw.get("PRICE_FILTER", {}), "tickSize"),
        "step_size": amount(lot, "stepSize"),
        "min_qty": amount(lot, "minQty"),
        "min_notional": max(minimums),
        "max_qty": amount(lot, "maxQty"),
        "market_min_qty": amount(market, "minQty"),
        "market_max_qty": amount(market, "maxQty"),
        "market_step_size": amount(market, "stepSize"),
        "max_notional": maximum,
        "notional_avg_price_mins": max(windows),
        "market_limits_known": all(
            all(name in item for name in ("minQty", "maxQty", "stepSize")) for item in (lot, market)
        )
        and bool(minimum or notional)
        and (not minimum or type(minimum.get("applyToMarket")) is bool)
        and (
            not notional
            or all(
                type(notional.get(flag)) is bool
                for flag in ("applyMinToMarket", "applyMaxToMarket")
            )
        ),
    }
    validate_market_rules(cast(MarketRules, SimpleNamespace(**values)))
    return values

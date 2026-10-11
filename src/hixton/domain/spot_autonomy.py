"""Pure, key-free Spot autonomy helpers used by Paper and historical Backtest.

These helpers never borrow funds, submit orders, request credentials or change
the frozen V8 product strategy. The research mode is optional and OFF by default.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, ROUND_DOWN

MAX_RESEARCH_SPOT_SLOTS = 4
FILLERS_WITH_POSITIVE_RESEARCH_HYPOTHESIS = frozenset(("NEARUSDC", "BCHUSDC"))
FILLER_CMO_RESEARCH_FLOOR = 0.20
_CENT = Decimal("0.01")


def _nonnegative(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


def marked_portfolio_equity(
    *,
    free_quote: Decimal,
    base_quantities: Mapping[str, Decimal],
    open_prices: Mapping[str, Decimal],
    dust_quantities: Mapping[str, Decimal] | None = None,
) -> Decimal:
    """A position is equity, not freely spendable USDC.

    Require a *fresh* price for every owned position and dust amount; no
    silent mark-to-zero or stale-price fallback. This is a Paper/Backtest model.
    """
    equity = _nonnegative(free_quote, "free_quote")
    for owned in (base_quantities, dust_quantities or {}):
        for symbol, qty in owned.items():
            qty = _nonnegative(qty, f"{symbol} quantity")
            if qty == 0:
                continue
            if symbol not in open_prices:
                raise ValueError(f"missing {symbol} mark price")
            price = _nonnegative(open_prices[symbol], f"{symbol} price")
            if price == 0:
                raise ValueError(f"{symbol} cannot have a zero execution price")
            equity += qty * price
    return equity


def size_spot_entry(
    *,
    equity: Decimal,
    free_quote: Decimal,
    slots: int,
    allocated_slots: int,
    reserve_fraction: Decimal = Decimal("0"),
) -> Decimal:
    """Reinvest gains/losses and cap a Spot entry by *actual free USDC*.

    Equity 1200 with 4 slots allocates 300 per slot. If 900 is already
    invested, free_quote may be 300; no reuse of committed capital.
    """
    equity = _nonnegative(equity, "portfolio equity")
    free_quote = _nonnegative(free_quote, "free quote")
    reserve_fraction = _nonnegative(reserve_fraction, "reserve fraction")
    if reserve_fraction >= 1:
        raise ValueError("reserve_fraction must be below 1")
    if type(slots) is not int or not 1 <= slots <= 10:
        raise ValueError("slots must be 1..10")
    if type(allocated_slots) is not int or not 1 <= allocated_slots <= slots:
        raise ValueError("allocated slots out of bounds")
    exposure = equity * (Decimal("1") - reserve_fraction)
    return min(
        (exposure * Decimal(allocated_slots) / Decimal(slots)).quantize(
            _CENT, rounding=ROUND_DOWN
        ),
        free_quote.quantize(_CENT, rounding=ROUND_DOWN),
    )


def quality_filler_block_reason(symbol: str, abs_cmo: float | None) -> str | None:
    """Causal experimental screen; never claim that it predicts wins."""
    if symbol not in FILLERS_WITH_POSITIVE_RESEARCH_HYPOTHESIS:
        return "SPOT_RESEARCH_FILLER_NOT_ELIGIBLE"
    if abs_cmo is None or not 0 <= abs_cmo <= 1:
        return "SPOT_RESEARCH_FILLER_INVALID_MOMENTUM"
    if abs_cmo < FILLER_CMO_RESEARCH_FLOOR:
        return "SPOT_RESEARCH_FILLER_WEAK_MOMENTUM"
    return None


def research_slot_allocations(
    ranked_candidates: Sequence[tuple[str, float | None]],
    *,
    free_slots: int,
    satellite_symbols: frozenset[str],
) -> dict[str, int]:
    """Allocate up to four concurrent slots, without forced use.

    Core-first routing is external and remains unchanged. Each eligible
    symbol gets one slot first; a single high-strength Core may get a
    *second* slot. Filler exposure never exceeds one slot per symbol.
    """
    if type(free_slots) is not int or free_slots < 0:
        raise ValueError("free_slots must be nonnegative integer")
    selected: list[tuple[str, float]] = []
    seen: set[str] = set()
    for symbol, raw_strength in ranked_candidates:
        if symbol in seen:
            continue
        seen.add(symbol)
        strength = max(0.0, float(raw_strength or 0.0))
        selected.append((symbol, strength))
    allocation = {symbol: 1 for symbol, _ in selected[:free_slots]}
    spare = max(0, free_slots - len(allocation))
    for symbol, strength in selected[:free_slots]:
        if spare <= 0:
            break
        if symbol not in satellite_symbols and strength >= 0.25:
            allocation[symbol] += 1
            spare -= 1
    return allocation


def reinvestment_capital(*, equity: Decimal, starting_cash: Decimal,
                         profit_fraction: Decimal = Decimal("1")) -> Decimal:
    """Causal research budget: keep a fraction of profits outside new exposure.

    Losses always reduce the available budget. Cash reserves are still marked
    as portfolio equity; this changes risk, never the drawdown denominator.
    """
    equity = _nonnegative(equity, "equity")
    starting_cash = _nonnegative(starting_cash, "starting_cash")
    profit_fraction = _nonnegative(profit_fraction, "profit_fraction")
    if starting_cash <= 0 or profit_fraction > 1:
        raise ValueError("positive seed and a profit fraction in 0..1 required")
    if equity <= starting_cash:
        return equity
    return starting_cash + (equity - starting_cash) * profit_fraction

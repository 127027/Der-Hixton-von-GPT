"""Causal capacity planning shared by Backtest, Paper and Live.

Twenty internal units represent one budget, not twenty trading slots.
Existing positions retain the capacity reserved at their entry.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from hixton.domain.allocation import allocate_entry_slots
from hixton.domain.spot_autonomy import size_spot_entry

TRANCHE_ALLOCATOR_VERSION = "CAPITAL-V2-HALVES-REST-DD10"
CAPACITY_UNITS = 20
HALF_UNITS = 10


def position_units(slot_count: int, allocation_units: int = 0) -> int:
    units = allocation_units or slot_count * HALF_UNITS
    if type(units) is not int or not 1 <= units <= CAPACITY_UNITS:
        raise ValueError("invalid position capacity")
    return units


def allocate_tranches(
    ranked_symbols: Sequence[str],
    *,
    free_units: int,
    policy: str,
    drawdown_pct: Decimal,
    trigger_pct: Decimal,
    existing_half: bool,
) -> tuple[dict[str, int], bool]:
    if type(free_units) is not int or not 0 <= free_units <= CAPACITY_UNITS:
        raise ValueError("invalid free capacity")
    if not drawdown_pct.is_finite() or not 0 <= drawdown_pct <= 100:
        raise ValueError("invalid finalized drawdown")
    if not trigger_pct.is_finite() or not 0 < trigger_pct < 100:
        raise ValueError("invalid split trigger")
    unique = tuple(dict.fromkeys(ranked_symbols))
    # Validate the policy even in the conditional branch.
    allocate_entry_slots((), free_slots=0, policy=policy)
    if drawdown_pct >= trigger_pct:
        if free_units == 20 and len(unique) >= 3:
            return dict(zip(unique[:3], (10, 5, 5), strict=True)), True
        if free_units == 10 and existing_half and len(unique) >= 2:
            return dict(zip(unique[:2], (5, 5), strict=True)), True
    base = allocate_entry_slots(unique, free_slots=(free_units + 9) // 10, policy=policy)
    remaining = free_units
    allocation: dict[str, int] = {}
    for symbol in unique:
        units = min(remaining, base.get(symbol, 0) * 10)
        if units:
            allocation[symbol] = units
            remaining -= units
    return allocation, False


def size_tranche(
    *,
    equity: Decimal,
    free_quote: Decimal,
    units: int,
    entry_fraction: Decimal,
) -> Decimal:
    position_units(1, units)
    if units % 10 == 0:
        return size_spot_entry(
            equity=equity,
            free_quote=free_quote,
            slots=2,
            allocated_slots=units // 10,
            reserve_fraction=Decimal(1) - entry_fraction,
        )
    return size_spot_entry(
        equity=equity,
        free_quote=free_quote,
        slots=1,
        allocated_slots=1,
        reserve_fraction=Decimal(1) - entry_fraction * Decimal(units) / Decimal(20),
    )

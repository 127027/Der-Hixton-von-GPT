"""Versioned 80-USDC slot allocation for portfolio validation."""

from __future__ import annotations

from collections.abc import Sequence

ONE_PER_SYMBOL = "one_per_symbol"
RANKED_REPEAT = "ranked_repeat"
SUPPORTED_SLOT_ALLOCATIONS = frozenset({ONE_PER_SYMBOL, RANKED_REPEAT})


def allocate_entry_slots(
    ranked_symbols: Sequence[str],
    *,
    free_slots: int,
    policy: str,
) -> dict[str, int]:
    """Give every ranked candidate one slot, then repeat the strongest if allowed."""

    if free_slots < 0:
        raise ValueError("free_slots may not be negative")
    if policy not in SUPPORTED_SLOT_ALLOCATIONS:
        raise ValueError(f"unsupported slot allocation policy: {policy}")
    unique = tuple(dict.fromkeys(ranked_symbols))
    allocation: dict[str, int] = {}
    for symbol in unique[:free_slots]:
        allocation[symbol] = 1
    remaining = free_slots - sum(allocation.values())
    if policy == RANKED_REPEAT and remaining > 0 and unique:
        allocation[unique[0]] = allocation.get(unique[0], 0) + remaining
    return allocation

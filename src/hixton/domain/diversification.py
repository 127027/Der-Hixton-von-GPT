"""Causal diversification decisions shared by historical and owned ledgers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from hixton.domain.spot_autonomy import size_spot_entry

DIVERSIFICATION_ALLOCATOR_VERSION = "CAPITAL-V3-LATCHED-DISTINCT"
StageSchedule = tuple[tuple[str, int], ...]


def validate_schedule(stages: StageSchedule) -> None:
    threshold = Decimal(0)
    count = 2
    for raw_threshold, slots in stages:
        value = Decimal(raw_threshold)
        if not value.is_finite() or value <= threshold:
            raise ValueError("diversification thresholds must increase and be positive")
        if type(slots) is not int or slots not in (3, 4, 6) or slots <= count:
            raise ValueError("diversification counts must increase through 3, 4 or 6")
        threshold, count = value, slots


def next_count(stages: StageSchedule, *, current: int, closed_equity: Decimal) -> int:
    validate_schedule(stages)
    if current not in (2, *(count for _, count in stages)):
        raise ValueError("persisted diversification count is not in strategy contract")
    if not closed_equity.is_finite() or closed_equity < 0:
        raise ValueError("diversification requires verified closed equity")
    return max(
        [current, *(slots for threshold, slots in stages if closed_equity >= Decimal(threshold))]
    )


def capacity_units(count: int) -> int:
    if count not in (3, 4, 6):
        raise ValueError("distinct allocation requires 3, 4 or 6 positions")
    return 20 // count


def distinct_allocations(
    ranked: Sequence[str], *, owned: Sequence[str], occupied_units: int, count: int
) -> dict[str, int]:
    if not 0 <= occupied_units <= 20:
        raise ValueError("invalid reserved diversification capacity")
    units = capacity_units(count)
    available = min(max(0, count - len(owned)), (20 - occupied_units) // units)
    candidates = tuple(symbol for symbol in dict.fromkeys(ranked) if symbol not in owned)
    return dict.fromkeys(candidates[:available], units)


def entry_budget(
    *, equity: Decimal, free_quote: Decimal, count: int, entry_fraction: Decimal
) -> Decimal:
    capacity_units(count)
    return size_spot_entry(
        equity=equity,
        free_quote=free_quote,
        slots=count,
        allocated_slots=1,
        reserve_fraction=Decimal(1) - entry_fraction,
    )


def trim_quantity(
    *, owned: Decimal, closed_equity: Decimal, close: Decimal, count: int, step: Decimal
) -> Decimal:
    capacity_units(count)
    if min(owned, closed_equity, close) <= 0 or step < 0:
        raise ValueError("trim requires positive owned quantity and closed valuation")
    target = closed_equity / Decimal(count) / close
    excess = max(Decimal(0), owned - target)
    return (excess / step).to_integral_value(rounding=ROUND_DOWN) * step if step else excess


def trim_signal_id(symbol: str, count: int, decision_close: datetime) -> str:
    if decision_close.tzinfo is None:
        raise ValueError("trim decision needs an aware finalized timestamp")
    capacity_units(count)
    return hashlib.sha256(
        f"DIVERSIFICATION_TRIM|{symbol}|{count}|{decision_close.isoformat()}".encode()
    ).hexdigest()

"""Single-source capital planning for backtest, Paper and Live.

Allocator V1 is the robust outcome of the exact-three-year 250/500/1000-USDC
research round: two ranked-repeat tranches, each using 50% of the configured
maximum capital. The first 1x50 real-money trial is deliberately separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from hixton.domain.allocation import RANKED_REPEAT

MIN_VALIDATED_CAPITAL_USDC = Decimal("100.00")
MAX_VALIDATED_CAPITAL_USDC = Decimal("1000.00")
DEFAULT_MAX_CAPITAL_USDC = Decimal("250.00")
ALLOCATOR_VERSION = "CAPITAL-V1-2X50PCT"
_CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CapitalPlan:
    max_capital_usdc: Decimal
    slot_count: int
    target_notional_usdc: Decimal
    reserve_usdc: Decimal
    allocation_policy: str
    version: str = ALLOCATOR_VERSION

    @property
    def max_commitment_usdc(self) -> Decimal:
        return self.target_notional_usdc * self.slot_count


def capital_plan(max_capital_usdc: Decimal) -> CapitalPlan:
    if not isinstance(max_capital_usdc, Decimal):
        max_capital_usdc = Decimal(str(max_capital_usdc))
    if not max_capital_usdc.is_finite():
        raise ValueError("max capital must be finite")
    normalized = max_capital_usdc.quantize(_CENT, rounding=ROUND_DOWN)
    if normalized < MIN_VALIDATED_CAPITAL_USDC:
        raise ValueError(
            f"max capital must be at least {MIN_VALIDATED_CAPITAL_USDC} USDC"
        )
    if normalized > MAX_VALIDATED_CAPITAL_USDC:
        raise ValueError(
            f"max capital currently validated only through {MAX_VALIDATED_CAPITAL_USDC} USDC"
        )
    slots = 2
    tranche = (normalized / slots).quantize(_CENT, rounding=ROUND_DOWN)
    reserve = normalized - tranche * slots
    if tranche < Decimal("50.00"):
        raise ValueError("derived tranche must be at least 50 USDC")
    return CapitalPlan(
        max_capital_usdc=normalized,
        slot_count=slots,
        target_notional_usdc=tranche,
        reserve_usdc=reserve,
        allocation_policy=RANKED_REPEAT,
    )

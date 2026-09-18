from __future__ import annotations

from hixton.domain.allocation import RANKED_REPEAT, allocate_entry_slots
from hixton.domain.versions import V6_COIN_STRATEGY


def test_v6_uses_owner_approved_repeat_capacity_with_daily_pause_only() -> None:
    from hixton.domain.risk import DAILY_LOSS_LIMIT_PCT

    assert V6_COIN_STRATEGY.slot_allocation == RANKED_REPEAT
    assert DAILY_LOSS_LIMIT_PCT == 5


def test_three_free_slots_are_fully_allocated_to_ranked_valid_candidates() -> None:
    assert sum(
        allocate_entry_slots(["BTCUSDC"], free_slots=3, policy=RANKED_REPEAT).values()
    ) == 3
    assert sum(
        allocate_entry_slots(
            ["BTCUSDC", "ETHUSDC"], free_slots=3, policy=RANKED_REPEAT
        ).values()
    ) == 3

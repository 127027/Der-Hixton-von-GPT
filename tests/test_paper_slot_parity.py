from __future__ import annotations

from hixton.domain.allocation import RANKED_REPEAT, allocate_entry_slots
from hixton.domain.versions import V6_COIN_STRATEGY


def test_v6_owner_slot_policy_matches_three_slot_examples() -> None:
    assert V6_COIN_STRATEGY.slot_allocation == RANKED_REPEAT
    assert allocate_entry_slots(["BTCUSDC"], free_slots=3, policy=RANKED_REPEAT) == {
        "BTCUSDC": 3
    }
    assert allocate_entry_slots(
        ["BTCUSDC", "ETHUSDC"], free_slots=3, policy=RANKED_REPEAT
    ) == {"BTCUSDC": 2, "ETHUSDC": 1}
    assert allocate_entry_slots(
        ["BTCUSDC", "ETHUSDC", "SOLUSDC"], free_slots=3, policy=RANKED_REPEAT
    ) == {"BTCUSDC": 1, "ETHUSDC": 1, "SOLUSDC": 1}


def test_dashboard_runtime_passes_same_slot_policy_to_paper_and_backtest() -> None:
    from inspect import getsource

    from hixton.runtime.continuity_supervisor import RuntimeSupervisor

    source = getsource(RuntimeSupervisor)
    assert "slot_allocation=self.strategy.slot_allocation" in source
    assert "slot_allocation=strategy.slot_allocation" in source

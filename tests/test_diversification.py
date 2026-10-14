"""Offline concentration, partial ownership and restart invariants."""

from decimal import Decimal as D

import pytest

from hixton.domain.diversification import (
    capacity_units,
    distinct_allocations,
    entry_budget,
    next_count,
    trim_quantity,
    validate_schedule,
)


def test_latched_stage_does_not_reconcentrate_after_drawdown_or_restart():
    stages = (("30000", 3), ("40000", 4), ("50000", 6))
    count = 2
    for equity, expected in ((29999, 2), (30000, 3), (29000, 3), (51000, 6), (10000, 6)):
        count = next_count(stages, current=count, closed_equity=D(equity))
        assert count == expected
    # A restored persisted six-position state remains six even at lower equity.
    assert next_count(stages, current=count, closed_equity=D(8000)) == 6


@pytest.mark.parametrize("count", (3, 4, 6))
def test_duplicate_signals_and_owned_coin_cannot_fill_multiple_positions(count):
    names = ("BTC", "BTC", "ETH", "SOL", "BNB", "ADA", "XRP", "DOGE")
    allocation = distinct_allocations(
        names, owned=("BTC",), occupied_units=capacity_units(count), count=count
    )
    assert "BTC" not in allocation
    assert len(allocation) == count - 1
    assert len(allocation) + 1 == count
    assert sum(allocation.values()) + capacity_units(count) <= 20


@pytest.mark.parametrize("count", (3, 4, 6))
def test_real_divisor_not_integer_capacity_bookkeeping_controls_spend(count):
    budget = entry_budget(equity=D(30000), free_quote=D(30000), count=count, entry_fraction=D(1))
    assert budget == D(30000) / count
    assert budget * count == D(30000)
    assert entry_budget(
        equity=D(30000), free_quote=D("9.99"), count=count, entry_fraction=D(1)
    ) == D("9.99")


def test_trim_is_decided_before_next_open_and_preserves_remaining_owned_quantity():
    sold = trim_quantity(
        owned=D(300), closed_equity=D(30000), close=D(100), count=3, step=D(".001")
    )
    assert sold == 200
    assert D(300) - sold == 100
    # Execution-price gaps may change proceeds but cannot change the frozen quantity.
    assert sold * D(80) == 16000
    assert sold * D(120) == 24000


@pytest.mark.parametrize(
    "stages",
    ((("30000", 3), ("25000", 4)), (("30000", 4), ("40000", 3)), (("0", 3),), (("NaN", 3),)),
)
def test_bad_stage_contract_is_rejected(stages):
    with pytest.raises(ValueError):
        validate_schedule(stages)


def test_invalid_persisted_stage_is_not_silently_repaired():
    with pytest.raises(ValueError):
        next_count((("30000", 3),), current=6, closed_equity=D(30000))


def test_unsupported_schedule_cannot_claim_active_live_capability():
    from dataclasses import replace

    from hixton.domain.versions import strategy_definition

    current = strategy_definition("v8r")
    assert current.autonomous_live_supported
    assert not replace(current, diversification_stages=()).autonomous_live_supported

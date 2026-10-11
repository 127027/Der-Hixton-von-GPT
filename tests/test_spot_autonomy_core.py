"""Offline Spot-autonomy invariants, with fixed V8 conservatism as default."""
from decimal import Decimal as D
import pytest

from hixton.domain.spot_autonomy import (
    marked_portfolio_equity, size_spot_entry, research_slot_allocations,
    quality_filler_block_reason,
)
from hixton.paper.models import PaperSettings


def test_compounding_uses_total_equity_not_per_trade_capital():
    assert size_spot_entry(equity=D("1100"),free_quote=D("1100"),slots=4,allocated_slots=1)==D("275.00")
    assert size_spot_entry(equity=D("1200"),free_quote=D("1200"),slots=4,allocated_slots=1)==D("300.00")
    assert size_spot_entry(equity=D("950"),free_quote=D("950"),slots=4,allocated_slots=1)==D("237.50")
    assert size_spot_entry(equity=D("1200"),free_quote=D("300"),slots=4,allocated_slots=3)==D("300.00")
    assert size_spot_entry(equity=D("1200"),free_quote=D("0"),slots=4,allocated_slots=1)==D("0.00")


def test_managed_equity_not_double_spent_when_held():
    equity=marked_portfolio_equity(
        free_quote=D("300"),
        base_quantities={"BTCUSDC":D("0.01"),"ETHUSDC":D("0.1")},
        open_prices={"BTCUSDC":D("50000"),"ETHUSDC":D("4000")},
    )
    assert equity==D("1200")
    assert size_spot_entry(equity=equity,free_quote=D("300"),slots=4,allocated_slots=1)==D("300.00")


def test_fails_closed_on_unknown_mark_and_incorrect_data():
    with pytest.raises(ValueError,match="missing"):
        marked_portfolio_equity(free_quote=D("700"),base_quantities={"BTCUSDC":D("0.1")},open_prices={})
    for bad in (D("NaN"),D("Infinity"),D("-1")):
        with pytest.raises(ValueError):
            size_spot_entry(equity=bad,free_quote=D("100"),slots=2,allocated_slots=1)
        with pytest.raises(ValueError):
            marked_portfolio_equity(free_quote=bad,base_quantities={},open_prices={})
    with pytest.raises(ValueError):
        size_spot_entry(equity=D("1100"),free_quote=D("1100"),slots=4,allocated_slots=5)


def test_research_slot_count_not_shared_by_default_mode():
    default=PaperSettings(max_capital_usdc=D("1100"))
    assert default.slot_count==2
    assert default.target_notional_usdc==D("550")
    research=PaperSettings(max_capital_usdc=D("1100"),autonomous_performance_enabled=True)
    assert research.slot_count==2
    assert research.target_notional_usdc==D("550")
    assert not research.auto_budget_enabled


def test_core_gets_double_only_with_quality_signal_and_capacity():
    x=research_slot_allocations(
        [("SOLUSDC",0.50),("BTCUSDC",0.10),("ETHUSDC",0.31)],
        free_slots=4,satellite_symbols=frozenset({"NEARUSDC","BCHUSDC"}))
    assert x=={"SOLUSDC":2,"BTCUSDC":1,"ETHUSDC":1}
    assert sum(x.values())<=4
    y=research_slot_allocations(
        [("NEARUSDC",0.88),("BCHUSDC",0.70)],
        free_slots=4,satellite_symbols=frozenset({"NEARUSDC","BCHUSDC"}))
    assert y=={"NEARUSDC":1,"BCHUSDC":1}


def test_weak_or_loss_making_research_fillers_blocked():
    assert quality_filler_block_reason("NEARUSDC",0.19)=="SPOT_RESEARCH_FILLER_WEAK_MOMENTUM"
    assert quality_filler_block_reason("NEARUSDC",0.20) is None
    assert quality_filler_block_reason("BCHUSDC",0.30) is None
    assert quality_filler_block_reason("AAVEUSDC",0.90)=="SPOT_RESEARCH_FILLER_NOT_ELIGIBLE"
    assert quality_filler_block_reason("SUIUSDC",0.90)=="SPOT_RESEARCH_FILLER_NOT_ELIGIBLE"

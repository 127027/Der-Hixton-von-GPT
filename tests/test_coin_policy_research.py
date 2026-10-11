"""Guard the research decision rules against profit-only or holdout selection."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import strategy_definition

_spec = spec_from_file_location(
    "coin_policy_research",
    Path(__file__).parents[1] / "scripts/research_coin_policies_20261011.py",
)
research = module_from_spec(_spec)
_spec.loader.exec_module(research)


def row(ret, dd, trades=10):
    return {"return_pct": str(ret), "dd_pct": str(dd), "trades": trades}


def test_large_training_profit_cannot_hide_worse_loss_year():
    base = [row(100, 40), row(-5, 20)]
    assert not research.train_eligible([row(300, 20), row(-6, 10)], base)


def test_lower_drawdown_cannot_pass_by_avoiding_almost_all_trades():
    base = [row(100, 40), row(20, 20)]
    assert not research.train_eligible([row(90, 10, 1), row(20, 10)], base)


def test_risk_reduction_requires_retaining_training_profit():
    base = [row(100, 40), row(20, 20)]
    assert not research.train_eligible([row(20, 10), row(10, 10)], base)
    assert research.train_eligible([row(80, 30), row(20, 15)], base)


def test_validation_cannot_be_rescued_by_only_one_cost_case():
    base = {"current": row(10, 30), "stress": row(-10, 40)}
    assert not research.validation_passes({"current": row(15, 20), "stress": row(-11, 20)}, base)
    assert not research.validation_passes({"current": row(15, 31), "stress": row(-5, 20)}, base)
    assert research.validation_passes({"current": row(8, 20), "stress": row(-5, 20)}, base)


def test_policy_research_preserves_existing_stricter_coin_gates():
    base = TradePolicy(cmo_floor=0.5, slope_bars=72, stop_atr=2, trail_atr=4)
    for name in research.CATALOGUE:
        assert research.policy_variant(base, name) == base
    with pytest.raises(ValueError, match="unknown"):
        research.policy_variant(base, "make_the_result_profitable")


def test_parameter_research_changes_one_indicator_and_preserves_policy():
    profile = strategy_definition("v8").coin_profiles[0]
    narrower = research.profile_variant(profile, "band80", "parameters")
    assert narrower.trade_policy == profile.trade_policy
    assert narrower.parameters.band_multiplier == 3.52
    assert narrower.parameters.atr_length == profile.parameters.atr_length
    assert profile.parameters.band_multiplier == 4.4
    assert research.profile_variant(profile, "baseline", "parameters") == profile
    with pytest.raises(ValueError, match="unknown"):
        research.profile_variant(profile, "more_profit", "parameters")


def test_hybrid_variant_retains_warmup_and_symbol_identity():
    profile = strategy_definition("v8").coin_profiles[0]
    hybrid = research.profile_variant(profile, "band80_slope24", "hybrid")
    assert hybrid.symbol == profile.symbol
    assert hybrid.parameters.warmup_bars == profile.parameters.warmup_bars
    assert hybrid.parameters.band_multiplier == 3.52
    assert hybrid.trade_policy.slope_bars == 24
    assert hybrid.trade_policy.cmo_floor == profile.trade_policy.cmo_floor

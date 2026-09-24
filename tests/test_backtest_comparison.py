from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal

import pytest

from hixton.backtest.comparison import compare_run
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.domain.versions import V6_COIN_STRATEGY as ACTIVE
from hixton.paper.models import PaperSettings


def evidence():
    manifest = {
        "quote_asset": "USDC",
        "strategy": {
            "version": ACTIVE.version,
            "parameters": None,
            "profiles": ACTIVE.profiles_payload(),
            "semantics": ACTIVE.semantics.value,
            "slot_allocation": ACTIVE.slot_allocation,
        },
        "validation_scope": {"python_source_sha256": "same"},
        "cost_models": {
            c.name: {k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(c).items()}
            for c in (BASELINE_COSTS, STRESS_COSTS)
        },
    }
    metrics = {
        "baseline": {
            "portfolio": {
                "slot_count": 2,
                "target_notional": "125.00",
                "starting_cash": "250",
                "risk_limits_applied": True,
            }
        }
    }
    return manifest, metrics


DEFAULT_SETTINGS = PaperSettings()


def compare(manifest, metrics, settings=DEFAULT_SETTINGS):
    return compare_run(
        manifest,
        metrics,
        active=ACTIVE,
        settings=settings,
        starting_cash=Decimal(250),
        source_hash="same",
    )


def test_matching_only_when_all_evidence_present_without_mutation():
    manifest, metrics = evidence()
    original = deepcopy((manifest, metrics))
    assert compare(manifest, metrics)["status"] == "MATCHING"
    assert (manifest, metrics) == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("slot_count", 3),
        ("target_notional", "100"),
        ("starting_cash", "240"),
        ("risk_limits_applied", False),
    ],
)
def test_changed_portfolio_settings_cannot_match(field, value):
    manifest, metrics = evidence()
    metrics["baseline"]["portfolio"][field] = value
    assert compare(manifest, metrics)["status"] == "DIFFERENT"


def test_old_quote_code_or_profile_cannot_match():
    for mutation in ("quote", "code", "profile"):
        manifest, metrics = evidence()
        if mutation == "quote":
            manifest["quote_asset"] = "USDT"
        elif mutation == "code":
            manifest["validation_scope"]["python_source_sha256"] = "old"
        else:
            manifest["strategy"]["profiles"]["DOTUSDC"]["parameters"]["band_multiplier"] = 2
        assert compare(manifest, metrics)["status"] == "DIFFERENT"


def test_missing_evidence_is_unknown_not_current():
    manifest, metrics = evidence()
    del manifest["cost_models"]
    assert compare(manifest, metrics)["status"] == "UNVERIFIED"
    manifest, metrics = evidence()
    assert compare(manifest, metrics, settings=None)["status"] == "UNVERIFIED"


def test_isolated_rules_match_but_model_difference_is_explicit():
    manifest, _ = evidence()
    result = compare(manifest, {"baseline": {"per_symbol": {"DOTUSDC": {}}}})
    assert result["status"] == "MATCHING"
    assert result["model"] == "ISOLATED"
    assert "kein permanenter Portfolio-Drawdown-Halt" in result["scope"]


def test_supervisor_refuses_new_backtest_after_source_change(tmp_path, monkeypatch):
    from hixton.runtime.supervisor import RuntimeSupervisor
    from tests.test_ui_api import _config

    supervisor = RuntimeSupervisor(_config(tmp_path))
    monkeypatch.setattr("hixton.backtest.reporting.source_fingerprint", lambda: "changed")
    with pytest.raises(RuntimeError, match="neu starten"):
        supervisor._synchronous_backtest("portfolio", None, "v2")

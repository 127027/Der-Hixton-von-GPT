from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.swarm_core import (
    AGENT_IDS,
    SwarmContractError,
    known_regression_requirements,
    load_mission,
    required_agents,
    required_evidence_by_agent,
    validate_active_mission_state,
    validate_cloud_patch_paths,
    validate_cloud_ready,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]


def test_registry_contains_exactly_all_eleven_cloud_agents() -> None:
    registry = validate_registry(ROOT)
    assert registry["agent_count"] == 11
    assert tuple(agent["id"] for agent in registry["agents"]) == AGENT_IDS
    assert registry["completion_contract"]["real_money_orders_allowed"] is False


def test_active_cloud_mission_requires_all_agents_and_current_v6_regression() -> None:
    mission = load_mission(ROOT)
    assert mission["id"] == "SWARM-003"
    assert mission["state"] == "IN_PROGRESS"
    assert mission["completion_mode"] == "continuous"
    assert set(required_agents(mission)) == set(AGENT_IDS)
    cases = known_regression_requirements(mission)
    assert "CURRENT_V6_PRODUCT" in cases
    assert "verify_current_v6_is_the_only_product_strategy" in cases["CURRENT_V6_PRODUCT"]
    assert "verify_assembled_10x250_and_max_budget_non_regression" in cases["CURRENT_V6_PRODUCT"]
    evidence = required_evidence_by_agent(mission)
    assert "topk_validation" in evidence["A02"]
    assert "portfolio_gate" in evidence["A02"]
    assert "public_kline_sample" in evidence["A07"]
    assert "evidence_contract_audit" in evidence["A10"]
    assert "governance_audit" in evidence["A11"]


def test_cloud_ready_summary_is_safe() -> None:
    summary = validate_cloud_ready(ROOT)
    assert summary["agent_count"] == 11
    assert summary["mission_id"] == "SWARM-003"
    assert summary["mission_state"] == "IN_PROGRESS"
    assert summary["execution"] == "github_actions_cloud"
    assert summary["real_money_orders_allowed"] is False
    assert summary["automatic_merge_allowed"] is False


def test_lifecycle_rejects_new_active_mission() -> None:
    mission = {
        "state": "NEW",
        "started_at_utc": datetime.now(UTC).isoformat(),
    }
    with pytest.raises(SwarmContractError, match="still NEW"):
        validate_active_mission_state(mission)


def test_lifecycle_rejects_future_start_time() -> None:
    mission = {
        "state": "IN_PROGRESS",
        "started_at_utc": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    with pytest.raises(SwarmContractError, match="cannot be in the future"):
        validate_active_mission_state(mission)


@pytest.mark.parametrize(
    "path",
    [
        "AGENTS.md",
        ".github/workflows/anything.yml",
        "agent_memory/swarm/agents/A01_documentation_requirements.md",
        "agent_memory/swarm/registry.json",
        "agent_memory/swarm/protocol.md",
        "src/hixton/live/exchange.py",
        "src/hixton/ui/live.py",
    ],
)
def test_cloud_patch_guard_rejects_governance_and_live_paths(path: str) -> None:
    with pytest.raises(SwarmContractError):
        validate_cloud_patch_paths([path])


def test_cloud_patch_guard_allows_normal_research_and_tests() -> None:
    assert validate_cloud_patch_paths(
        [
            "src/hixton/backtest/portfolio_review.py",
            "tests/test_portfolio_review.py",
            "backtests/v10/README.md",
        ]
    ) == (
        "backtests/v10/README.md",
        "src/hixton/backtest/portfolio_review.py",
        "tests/test_portfolio_review.py",
    )

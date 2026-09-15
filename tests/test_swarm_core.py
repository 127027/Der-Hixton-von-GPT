from pathlib import Path

import pytest

from scripts.swarm_core import (
    AGENT_IDS,
    SwarmContractError,
    known_regression_requirements,
    load_mission,
    required_agents,
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


def test_active_cloud_mission_requires_all_agents_and_quote_regression() -> None:
    mission = load_mission(ROOT)
    assert mission["id"] == "SWARM-002"
    assert set(required_agents(mission)) == set(AGENT_IDS)
    cases = known_regression_requirements(mission)
    assert "USDT_USDC_MIGRATION" in cases
    assert "compare_exact_same_window" in cases["USDT_USDC_MIGRATION"]
    assert "separate_running_account_path_from_fresh_start" in cases["USDT_USDC_MIGRATION"]


def test_cloud_ready_summary_is_safe() -> None:
    summary = validate_cloud_ready(ROOT)
    assert summary["agent_count"] == 11
    assert summary["mission_id"] == "SWARM-002"
    assert summary["execution"] == "github_actions_cloud"
    assert summary["real_money_orders_allowed"] is False
    assert summary["automatic_merge_allowed"] is False


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

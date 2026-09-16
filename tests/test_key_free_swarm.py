from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import cloud_swarm_agent
from scripts.swarm_core import (
    AGENT_IDS,
    load_mission,
    required_evidence_by_agent,
)


def _contract() -> dict[str, tuple[str, ...]]:
    mission = load_mission(cloud_swarm_agent.ROOT)
    return required_evidence_by_agent(mission)


def _write_reports(root: Path, agents: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    contract = _contract()
    for agent in agents:
        payload: dict[str, object] = {
            "agent": agent,
            "verdict": "PASS",
            "evidence": [{"coverage_tags": list(contract[agent])}],
        }
        if agent == "A10":
            payload["evidence"] = [
                {
                    "evidence_contract_passed": True,
                    "repair_required": False,
                    "coverage_tags": list(contract[agent]),
                }
            ]
        if agent == "A09":
            payload["gate"] = "QA_PASS"
        (root / f"{agent}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_all_eleven_roles_are_registered() -> None:
    assert tuple(f"A{i:02d}" for i in range(1, 12)) == AGENT_IDS
    assert set(cloud_swarm_agent.SIMPLE_ROLES) == {
        f"A{i:02d}" for i in range(1, 9)
    }


def test_taskboard_declares_key_free_paper_only_runtime_and_active_guard() -> None:
    board_path = cloud_swarm_agent.ROOT / "agent_memory/swarm/taskboard.json"
    board = json.loads(board_path.read_text(encoding="utf-8"))
    runtime = board["agent_runtime"]
    assert runtime["agent_execution_mode"] == "deterministic_key_free"
    assert runtime["openai_api_key_required"] is False
    assert runtime["trading_mode"] == "paper_only"
    assert runtime["real_money_orders_allowed"] is False
    assert runtime["testnet_orders_allowed"] is False
    assert runtime["binance_private_credentials_allowed"] is False
    assert board["active_mission"]["state"] == "IN_PROGRESS"
    assert board["active_mission"]["completion_mode"] == "continuous"
    assert board["active_mission"]["id"] == "SWARM-003"


def test_a10_accepts_complete_specialist_evidence(tmp_path: Path) -> None:
    _write_reports(tmp_path, [f"A{i:02d}" for i in range(1, 9)])
    evidence = cloud_swarm_agent.role_a10(tmp_path)
    assert evidence[0]["repair_required"] is False
    assert evidence[0]["evidence_contract_passed"] is True


def test_a10_rejects_pass_without_required_evidence(tmp_path: Path) -> None:
    _write_reports(tmp_path, [f"A{i:02d}" for i in range(1, 9)])
    a02 = json.loads((tmp_path / "A02.json").read_text(encoding="utf-8"))
    a02["evidence"] = [{"coverage_tags": ["same_window_comparison"]}]
    (tmp_path / "A02.json").write_text(json.dumps(a02), encoding="utf-8")
    with pytest.raises(cloud_swarm_agent.CheckFailure, match="evidence_missing"):
        cloud_swarm_agent.role_a10(tmp_path)


def test_a09_requires_clean_a10_repair_state(tmp_path: Path, monkeypatch) -> None:
    _write_reports(tmp_path, [f"A{i:02d}" for i in range(1, 11) if i != 9])
    a10 = json.loads((tmp_path / "A10.json").read_text(encoding="utf-8"))
    a10["evidence"][0]["repair_required"] = True
    (tmp_path / "A10.json").write_text(json.dumps(a10), encoding="utf-8")
    monkeypatch.setattr(cloud_swarm_agent, "require_command", lambda *args, **kwargs: {})
    with pytest.raises(cloud_swarm_agent.CheckFailure, match="upstream contract incomplete"):
        cloud_swarm_agent.role_a09(tmp_path)


def test_a11_requires_qa_pass_all_prior_roles_and_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    _write_reports(tmp_path, [f"A{i:02d}" for i in range(1, 11)])
    monkeypatch.setattr(cloud_swarm_agent, "paper_runtime_contract", lambda: {})
    monkeypatch.setattr(
        cloud_swarm_agent,
        "validate_cloud_ready",
        lambda root: {"mission_id": "SWARM-003", "mission_state": "IN_PROGRESS"},
    )
    evidence = cloud_swarm_agent.role_a11(tmp_path)
    assert evidence[0]["governance"] == "GOVERNANCE_PASS"
    assert evidence[0]["evidence_contract_passed"] is True


def test_a11_rejects_missing_specialist_coverage(tmp_path: Path, monkeypatch) -> None:
    _write_reports(tmp_path, [f"A{i:02d}" for i in range(1, 11)])
    a07 = json.loads((tmp_path / "A07.json").read_text(encoding="utf-8"))
    a07["evidence"] = [{"coverage_tags": []}]
    (tmp_path / "A07.json").write_text(json.dumps(a07), encoding="utf-8")
    monkeypatch.setattr(cloud_swarm_agent, "paper_runtime_contract", lambda: {})
    monkeypatch.setattr(
        cloud_swarm_agent,
        "validate_cloud_ready",
        lambda root: {"mission_id": "SWARM-003", "mission_state": "IN_PROGRESS"},
    )
    with pytest.raises(cloud_swarm_agent.CheckFailure, match="evidence_missing"):
        cloud_swarm_agent.role_a11(tmp_path)

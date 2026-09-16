from __future__ import annotations

import json
from pathlib import Path

from scripts import cloud_swarm_agent
from scripts.swarm_core import AGENT_IDS


def _write_reports(root: Path, agents: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for agent in agents:
        payload = {"agent": agent, "verdict": "PASS"}
        if agent == "A09":
            payload["gate"] = "QA_PASS"
        (root / f"{agent}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_all_eleven_roles_are_registered() -> None:
    assert tuple(f"A{i:02d}" for i in range(1, 12)) == AGENT_IDS
    assert set(cloud_swarm_agent.SIMPLE_ROLES) == {
        f"A{i:02d}" for i in range(1, 9)
    }


def test_taskboard_declares_key_free_paper_only_runtime() -> None:
    board_path = cloud_swarm_agent.ROOT / "agent_memory/swarm/taskboard.json"
    board = json.loads(board_path.read_text(encoding="utf-8"))
    runtime = board["agent_runtime"]
    assert runtime["agent_execution_mode"] == "deterministic_key_free"
    assert runtime["openai_api_key_required"] is False
    assert runtime["trading_mode"] == "paper_only"
    assert runtime["real_money_orders_allowed"] is False
    assert runtime["testnet_orders_allowed"] is False
    assert runtime["binance_private_credentials_allowed"] is False


def test_a10_accepts_complete_specialist_evidence(tmp_path: Path) -> None:
    _write_reports(tmp_path, [f"A{i:02d}" for i in range(1, 9)])
    evidence = cloud_swarm_agent.role_a10(tmp_path)
    assert evidence[0]["repair_required"] is False


def test_a11_requires_qa_pass_and_all_prior_roles(tmp_path: Path, monkeypatch) -> None:
    _write_reports(tmp_path, [f"A{i:02d}" for i in range(1, 11)])
    monkeypatch.setattr(cloud_swarm_agent, "paper_runtime_contract", lambda: {})
    evidence = cloud_swarm_agent.role_a11(tmp_path)
    assert evidence[0]["governance"] == "GOVERNANCE_PASS"

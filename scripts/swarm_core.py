"""Pure contracts for the GitHub-hosted Hixton engineering swarm.

This module is standard-library only, imports no trading runtime and performs no
network or exchange action. GitHub Actions uses it to validate the eleven-agent
registry, active mission and protected patch boundaries before model work starts.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

AGENT_IDS = tuple(f"A{i:02d}" for i in range(1, 12))
MANDATORY_AGENTS = frozenset(AGENT_IDS)

KNOWN_REGRESSION_CASES: dict[str, tuple[str, ...]] = {
    "USDT_USDC_MIGRATION": (
        "compare_exact_same_window",
        "separate_running_account_path_from_fresh_start",
        "verify_real_quote_specific_candle_history_and_listing_window",
        "verify_portfolio_risk_halt_and_slot_block_reasons",
        "verify_paper_shared_portfolio_parity_when_account_assumptions_match",
        "verify_ui_and_report_quote_provenance",
        "do_not_patch_without_a_proven_code_or_contract_defect",
    ),
}

PROTECTED_EXACT_PATHS = frozenset(
    {
        "AGENTS.md",
        "agent_memory/swarm/registry.json",
        "agent_memory/swarm/protocol.md",
        "src/hixton/ui/live.py",
    }
)
PROTECTED_PREFIXES = (
    ".github/",
    "agent_memory/swarm/agents/",
    "src/hixton/live/",
)


class SwarmContractError(ValueError):
    """Raised when repository state violates the cloud-swarm contract."""


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SwarmContractError(f"Expected JSON object: {path}")
    return value


def validate_registry(repo: Path) -> dict[str, Any]:
    root = repo / "agent_memory" / "swarm"
    registry = load_json(root / "registry.json")
    agents = registry.get("agents")
    if not isinstance(agents, list):
        raise SwarmContractError("registry.agents must be a list")
    ids = tuple(item.get("id") for item in agents if isinstance(item, dict))
    if ids != AGENT_IDS:
        raise SwarmContractError(f"Registry must contain A01..A11 in order, got {ids!r}")
    if registry.get("agent_count") != 11:
        raise SwarmContractError("registry.agent_count must be 11")
    for item in agents:
        if not isinstance(item, dict):
            raise SwarmContractError("Every registry agent must be an object")
        role = item.get("role_file")
        if not isinstance(role, str) or not role:
            raise SwarmContractError(f"Missing role_file for {item.get('id')}")
        if not (root / role).is_file():
            raise SwarmContractError(f"Missing role contract: {role}")
    completion = registry.get("completion_contract")
    if not isinstance(completion, dict):
        raise SwarmContractError("registry.completion_contract must be an object")
    if completion.get("real_money_orders_allowed") is not False:
        raise SwarmContractError("Autonomous swarm must never allow real-money orders")
    return registry


def _mission_candidates(board: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    active = board.get("active_mission")
    if isinstance(active, dict):
        result.append(active)
    queued = board.get("queued_missions")
    if isinstance(queued, list):
        result.extend(item for item in queued if isinstance(item, dict))
    completed = board.get("completed_missions")
    if isinstance(completed, list):
        result.extend(item for item in completed if isinstance(item, dict))
    return result


def load_mission(repo: Path, mission_id: str | None = None) -> dict[str, Any]:
    board = load_json(repo / "agent_memory" / "swarm" / "taskboard.json")
    if mission_id is None:
        active = board.get("active_mission")
        if not isinstance(active, dict):
            raise SwarmContractError("No active mission is configured")
        return active
    for mission in _mission_candidates(board):
        if mission.get("id") == mission_id:
            return mission
    raise SwarmContractError(f"Unknown mission: {mission_id}")


def required_agents(mission: dict[str, Any]) -> tuple[str, ...]:
    configured = mission.get("required_agents")
    if not isinstance(configured, list):
        raise SwarmContractError("mission.required_agents must be a list")
    ids = tuple(str(value) for value in configured)
    if len(ids) != 11 or len(set(ids)) != 11 or set(ids) != MANDATORY_AGENTS:
        raise SwarmContractError(
            "Material cloud missions must explicitly require every agent A01..A11"
        )
    return ids


def known_regression_requirements(mission: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    cases = mission.get("regression_cases") or []
    if not isinstance(cases, list):
        raise SwarmContractError("mission.regression_cases must be a list")
    result: dict[str, tuple[str, ...]] = {}
    for raw in cases:
        case = str(raw)
        try:
            result[case] = KNOWN_REGRESSION_CASES[case]
        except KeyError as error:
            raise SwarmContractError(f"Unknown regression case: {case}") from error
    return result


def normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def validate_cloud_patch_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """Reject autonomous edits to swarm governance and unreleased Live submit code."""
    normalized = tuple(sorted({normalize_repo_path(path) for path in paths if path.strip()}))
    bad = tuple(
        path
        for path in normalized
        if path in PROTECTED_EXACT_PATHS
        or any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
    )
    if bad:
        raise SwarmContractError(f"Autonomous patch touched protected paths: {bad}")
    return normalized


def validate_cloud_ready(repo: Path) -> dict[str, Any]:
    registry = validate_registry(repo)
    mission = load_mission(repo)
    agents = required_agents(mission)
    regressions = known_regression_requirements(mission)
    return {
        "agent_count": registry["agent_count"],
        "mission_id": mission.get("id"),
        "mission_state": mission.get("state"),
        "required_agents": list(agents),
        "regression_cases": sorted(regressions),
        "real_money_orders_allowed": False,
        "automatic_merge_allowed": False,
        "execution": "github_actions_cloud",
    }

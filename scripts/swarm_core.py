"""Pure contracts for the GitHub-hosted Hixton engineering swarm.

This module is standard-library only, imports no trading runtime and performs no
network or exchange action. GitHub Actions uses it to validate the eleven-agent
registry, active mission, lifecycle state, evidence contract and protected patch
boundaries before specialist work can be accepted.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

AGENT_IDS = tuple(f"A{i:02d}" for i in range(1, 12))
MANDATORY_AGENTS = frozenset(AGENT_IDS)

ACTIVE_MISSION_STATES = frozenset(
    {
        "PREFLIGHT",
        "ASSIGNED",
        "IN_PROGRESS",
        "VERIFYING",
        "REGRESSION",
        "QA",
        "GOVERNANCE",
        "REPAIR_LOOP",
    }
)

KNOWN_REGRESSION_CASES: dict[str, tuple[str, ...]] = {
    "CURRENT_V6_PRODUCT": (
        "verify_current_v6_is_the_only_product_strategy",
        "verify_canonical_profile_source_has_no_runtime_config_copy",
        "verify_topk_train_validation_full_stress_contract",
        "verify_each_robust_coin_candidate_in_shared_3x80",
        "verify_assembled_10x250_and_3x80_non_regression",
        "verify_paper_shared_portfolio_parity",
        "verify_paper_state_freshness_and_persistence",
        "verify_public_binance_usdc_market_data",
        "verify_current_ui_and_documentation_surface",
        "verify_full_regression_and_release_governance",
    ),
}

REGRESSION_EVIDENCE_CONTRACTS: dict[str, dict[str, tuple[str, ...]]] = {
    "CURRENT_V6_PRODUCT": {
        "A01": ("requirements_contract", "paper_only_contract", "mission_lifecycle"),
        "A02": ("current_v6_backtest", "topk_validation", "portfolio_gate"),
        "A03": ("paper_shared_parity", "persistent_paper_state"),
        "A04": ("current_v6_ui", "shipped_ui_bundle"),
        "A05": ("runtime_freshness", "ledger_integrity"),
        "A06": ("integration_compile", "full_regression"),
        "A07": ("binance_usdc_universe", "public_kline_sample"),
        "A08": ("strategy_risk_invariants", "loss_analysis"),
        "A09": ("independent_full_qa", "independent_ui_qa"),
        "A10": ("evidence_contract_audit", "repair_routing"),
        "A11": ("governance_audit",),
    },
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


def validate_active_mission_state(mission: dict[str, Any]) -> str:
    state = str(mission.get("state") or "")
    if state == "NEW":
        raise SwarmContractError(
            "Active mission is still NEW. The lifecycle guard must normalize it to "
            "IN_PROGRESS before specialist evidence is accepted."
        )
    if state == "BLOCKED":
        raise SwarmContractError("Active mission is BLOCKED and cannot pass normal execution")
    if state == "DONE":
        raise SwarmContractError("A DONE mission cannot remain the active mission")
    if state not in ACTIVE_MISSION_STATES:
        raise SwarmContractError(f"Unknown or invalid active mission state: {state!r}")

    raw_started = mission.get("started_at_utc")
    if not isinstance(raw_started, str) or not raw_started:
        raise SwarmContractError("Active mission must record started_at_utc")
    try:
        started = datetime.fromisoformat(raw_started)
    except ValueError as error:
        raise SwarmContractError("Active mission started_at_utc is not valid ISO-8601") from error
    if started.tzinfo is None:
        raise SwarmContractError("Active mission started_at_utc must be timezone-aware")
    if started.astimezone(UTC) > datetime.now(UTC) + timedelta(minutes=5):
        raise SwarmContractError("Active mission started_at_utc cannot be in the future")
    return state


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


def required_evidence_by_agent(mission: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    cases = mission.get("regression_cases") or []
    if not isinstance(cases, list):
        raise SwarmContractError("mission.regression_cases must be a list")
    merged: dict[str, set[str]] = {agent: set() for agent in AGENT_IDS}
    for raw in cases:
        case = str(raw)
        try:
            contract = REGRESSION_EVIDENCE_CONTRACTS[case]
        except KeyError as error:
            raise SwarmContractError(
                f"Missing evidence contract for regression case: {case}"
            ) from error
        for agent, tags in contract.items():
            merged[agent].update(tags)
    return {agent: tuple(sorted(tags)) for agent, tags in merged.items()}


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
    state = validate_active_mission_state(mission)
    agents = required_agents(mission)
    regressions = known_regression_requirements(mission)
    evidence = required_evidence_by_agent(mission)
    return {
        "agent_count": registry["agent_count"],
        "mission_id": mission.get("id"),
        "mission_state": state,
        "required_agents": list(agents),
        "regression_cases": sorted(regressions),
        "required_evidence_by_agent": {key: list(value) for key, value in evidence.items()},
        "real_money_orders_allowed": False,
        "automatic_merge_allowed": False,
        "execution": "github_actions_cloud",
    }

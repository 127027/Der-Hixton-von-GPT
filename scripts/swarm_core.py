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
    "USDT_USDC_MIGRATION": (
        "compare_exact_same_window",
        "separate_running_account_path_from_fresh_start",
        "verify_real_quote_specific_candle_history_and_listing_window",
        "verify_portfolio_risk_halt_and_slot_block_reasons",
        "verify_paper_shared_portfolio_parity_when_account_assumptions_match",
        "verify_ui_and_report_quote_provenance",
        "verify_fresh_dual_quote_replay",
        "verify_three_year_strategy_continuity",
        "distinguish_shared_portfolio_from_isolated_accounts",
        "do_not_patch_without_a_proven_code_or_contract_defect",
    ),
}

REGRESSION_EVIDENCE_CONTRACTS: dict[str, dict[str, tuple[str, ...]]] = {
    "USDT_USDC_MIGRATION": {
        "A01": ("requirements_contract", "paper_only_contract", "mission_lifecycle"),
        "A02": ("same_window_comparison", "carried_vs_fresh", "quote_migration_diagnosis"),
        "A03": ("paper_shared_parity", "persistent_paper_state"),
        "A04": ("ui_quote_provenance", "shipped_ui_bundle"),
        "A05": ("runtime_freshness", "ledger_integrity"),
        "A06": ("integration_compile", "full_regression"),
        "A07": ("binance_usdc_universe", "public_kline_sample"),
        "A08": ("strategy_risk_invariants", "early_loss_risk_path"),
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


def validate_migration_research_evidence(repo: Path) -> dict[str, Any]:
    """Require durable fresh evidence for the USDT/USDC history-window diagnosis."""
    reports = repo / "backtests" / "v8" / "reports"
    fresh = load_json(reports / "fresh-quote-replay-20260916.json")
    proxy = load_json(reports / "three-year-usdc-strategy-proxy-20260916.json")

    if fresh.get("classification") != "NON_EQUIVALENT_HISTORY_WINDOW_DOMINATES":
        raise SwarmContractError("fresh dual-quote replay has unexpected classification")
    if fresh.get("profiles_identical_by_base_asset") is not True:
        raise SwarmContractError("fresh USDT/USDC profiles are not identical by base asset")
    if fresh.get("fresh_common_start_utc") != "2024-03-24T00:00:00+00:00":
        raise SwarmContractError("fresh USDT/USDC common start drifted")

    portfolio = fresh.get("portfolio_3x80")
    isolated = fresh.get("isolated_10x250")
    history = fresh.get("real_usdc_history")
    branches = (portfolio, isolated, history)
    if not all(isinstance(item, dict) for item in branches):
        raise SwarmContractError("fresh dual-quote report is incomplete")
    if portfolio.get("same_window_usdc_minus_usdt") != "2.51522026442150000000":
        raise SwarmContractError("same-window USDT/USDC delta drifted")
    if history.get("limiting_symbol") != "DOGEUSDC":
        raise SwarmContractError("real USDC common-history limiting symbol drifted")
    if history.get("ten_market_common_usable_start_utc") != "2024-03-24T00:00:00+00:00":
        raise SwarmContractError("real USDC ten-market history start drifted")

    usdt_full = portfolio.get("usdt_full")
    usdt_common = portfolio.get("usdt_fresh_common")
    usdc_common = portfolio.get("usdc_fresh_common")
    if not all(isinstance(item, dict) for item in (usdt_full, usdt_common, usdc_common)):
        raise SwarmContractError("portfolio replay branches are incomplete")
    if usdt_full.get("ending_equity") != "733.30648172557635000000":
        raise SwarmContractError("full-window USDT portfolio reference drifted")
    if usdt_common.get("ending_equity") != "201.1088399751235000000":
        raise SwarmContractError("same-window fresh USDT portfolio reference drifted")
    if usdc_common.get("ending_equity") != "203.62406023954500000000":
        raise SwarmContractError("same-window fresh USDC portfolio reference drifted")
    if usdt_common.get("risk_halted_at_utc") == usdt_full.get("risk_halted_at_utc"):
        raise SwarmContractError("fresh and carried/full risk paths were collapsed together")

    if isolated.get("usdt_full_ending_equity") != "7152.29370844759090000000":
        raise SwarmContractError("full-window USDT isolated-batch reference drifted")
    if isolated.get("usdt_fresh_common_ending_equity") != "4118.70147055677790000000":
        raise SwarmContractError("same-window fresh USDT isolated-batch reference drifted")
    if isolated.get("usdc_fresh_common_ending_equity") != "4007.26179461508830000000":
        raise SwarmContractError("same-window fresh USDC isolated-batch reference drifted")

    if proxy.get("research_mode") != "USDT_BASE_MARKET_PROXY_FOR_CURRENT_USDC_STRATEGY":
        raise SwarmContractError("three-year strategy continuity evidence is not labelled as proxy")
    finding = proxy.get("finding")
    baseline = proxy.get("baseline")
    if not isinstance(finding, dict) or not isinstance(baseline, dict):
        raise SwarmContractError("three-year strategy continuity report is incomplete")
    if finding.get("full_three_year_schema_f_reproduced") is not True:
        raise SwarmContractError("current USDC schema did not reproduce three-year continuity")
    proxy_portfolio = baseline.get("portfolio_3x80")
    proxy_isolated = baseline.get("isolated_10x250")
    if not isinstance(proxy_portfolio, dict) or not isinstance(proxy_isolated, dict):
        raise SwarmContractError("three-year proxy baseline branches are incomplete")
    if proxy_portfolio.get("ending_equity") != "733.30648172557635000000":
        raise SwarmContractError("current USDC strategy three-year portfolio continuity drifted")
    if proxy_isolated.get("ending_equity") != "7152.29370844759090000000":
        raise SwarmContractError("current USDC strategy three-year isolated continuity drifted")

    return {
        "fresh_common_start_utc": fresh["fresh_common_start_utc"],
        "limiting_usdc_symbol": history["limiting_symbol"],
        "same_window_usdt_ending": usdt_common["ending_equity"],
        "same_window_usdc_ending": usdc_common["ending_equity"],
        "three_year_portfolio_ending": proxy_portfolio["ending_equity"],
        "three_year_isolated_ending": proxy_isolated["ending_equity"],
        "classification": fresh["classification"],
        "proxy_labelled": True,
    }


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
    migration_evidence: dict[str, Any] | None = None
    if "USDT_USDC_MIGRATION" in regressions:
        migration_evidence = validate_migration_research_evidence(repo)
    return {
        "agent_count": registry["agent_count"],
        "mission_id": mission.get("id"),
        "mission_state": state,
        "required_agents": list(agents),
        "regression_cases": sorted(regressions),
        "required_evidence_by_agent": {key: list(value) for key, value in evidence.items()},
        "migration_research_evidence": migration_evidence,
        "real_money_orders_allowed": False,
        "automatic_merge_allowed": False,
        "execution": "github_actions_cloud",
    }

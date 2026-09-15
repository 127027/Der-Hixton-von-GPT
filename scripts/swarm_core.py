"""Pure orchestration rules for the local Hixton engineering swarm.

This module has no trading-runtime imports and no exchange/network side effects.
It is intentionally standard-library only so the orchestration contract can be
unit-tested separately from the bot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
import json

AGENT_IDS = tuple(f"A{i:02d}" for i in range(1, 12))

# A10 plans first. A01 establishes the document/requirement contract. A11 audits
# the assignment before specialist work, then runs again as the final governance
# gate. Specialists are deliberately all consulted: an unaffected agent may
# return NOT_APPLICABLE, but it cannot be silently omitted.
SPECIALIST_ORDER = ("A07", "A08", "A02", "A03", "A04", "A05")
REVIEW_ORDER = ("A06", "A09", "A11")

REPORT_VERDICTS = {
    "PASS",
    "FAIL",
    "BLOCKED",
    "NOT_APPLICABLE",
    "QA_PASS",
    "QA_FAIL",
    "GOVERNANCE_PASS",
    "GOVERNANCE_FAIL",
}

# These files are not forbidden from ever changing; they are forbidden from
# being changed by an ordinary generic improvement mission. A future real-money
# release needs an explicit owner mission with allow_live_release=true.
PROTECTED_LIVE_PREFIXES = (
    "src/hixton/live/",
    "src/hixton/ui/live.py",
)

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


class SwarmContractError(ValueError):
    """Raised when a plan/report/runtime transition violates the swarm contract."""


def utc_now_text() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SwarmContractError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_registry(repo: Path) -> dict[str, Any]:
    registry = load_json(repo / "agent_memory" / "swarm" / "registry.json")
    agents = registry.get("agents")
    if not isinstance(agents, list):
        raise SwarmContractError("registry.agents must be a list")
    ids = tuple(item.get("id") for item in agents if isinstance(item, dict))
    if ids != AGENT_IDS:
        raise SwarmContractError(f"Registry must contain A01..A11 in order, got {ids!r}")
    if registry.get("agent_count") != 11:
        raise SwarmContractError("registry.agent_count must be 11")
    for item in agents:
        role = item.get("role_file")
        if not isinstance(role, str) or not role:
            raise SwarmContractError(f"Missing role_file for {item.get('id')}")
        if not (repo / "agent_memory" / "swarm" / role).is_file():
            raise SwarmContractError(f"Missing role contract: {role}")
    return registry


def load_mission(repo: Path, mission_id: str | None = None) -> dict[str, Any]:
    board = load_json(repo / "agent_memory" / "swarm" / "taskboard.json")
    candidates: list[dict[str, Any]] = []
    active = board.get("active_mission")
    if isinstance(active, dict):
        candidates.append(active)
    queued = board.get("queued_missions")
    if isinstance(queued, list):
        candidates.extend(item for item in queued if isinstance(item, dict))
    if mission_id is None:
        if not candidates:
            raise SwarmContractError("No mission is available")
        return candidates[0]
    for mission in candidates:
        if mission.get("id") == mission_id:
            return mission
    raise SwarmContractError(f"Unknown mission: {mission_id}")


def required_agents(mission: dict[str, Any]) -> tuple[str, ...]:
    configured = mission.get("required_agents")
    if configured is None:
        # Hixton defaults to full-swarm review. This is intentionally expensive:
        # the user's goal is regression prevention rather than minimal token use.
        return AGENT_IDS
    if not isinstance(configured, list):
        raise SwarmContractError("mission.required_agents must be a list")
    ids = tuple(str(value) for value in configured)
    if len(set(ids)) != len(ids) or any(value not in AGENT_IDS for value in ids):
        raise SwarmContractError(f"Invalid mission.required_agents: {ids!r}")
    mandatory = {"A01", "A06", "A09", "A10", "A11"}
    if not mandatory.issubset(ids):
        raise SwarmContractError(
            "Every material mission requires A01, A06, A09, A10 and A11"
        )
    return ids


def execution_sequence(mission: dict[str, Any]) -> tuple[str, ...]:
    required = set(required_agents(mission))
    ordered = ["A10", "A01", "A11"]  # A11 assignment/governance audit phase 1.
    ordered.extend(agent for agent in SPECIALIST_ORDER if agent in required)
    ordered.extend(agent for agent in ("A06", "A09", "A11") if agent in required)
    # A11 intentionally appears twice: assignment audit and final governance.
    return tuple(ordered)


def known_regression_requirements(mission: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    cases = mission.get("regression_cases") or []
    if not isinstance(cases, list):
        raise SwarmContractError("mission.regression_cases must be a list")
    result: dict[str, tuple[str, ...]] = {}
    for case in cases:
        case_id = str(case)
        if case_id not in KNOWN_REGRESSION_CASES:
            raise SwarmContractError(f"Unknown regression case: {case_id}")
        result[case_id] = KNOWN_REGRESSION_CASES[case_id]
    return result


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SwarmContractError(f"{field} must be a list of strings")
    return list(value)


def validate_plan(
    plan: dict[str, Any], mission: dict[str, Any], *, allow_coordinator_patch: bool = False
) -> dict[str, Any]:
    if plan.get("mission_id") != mission.get("id"):
        raise SwarmContractError("plan mission_id does not match taskboard mission")
    plan_required = _string_list(plan.get("required_agents"), "plan.required_agents")
    mission_required = set(required_agents(mission))
    if set(plan_required) != mission_required:
        raise SwarmContractError(
            "A10 may order agents, but may not silently omit/add required agents"
        )
    patch_owner = plan.get("patch_owner")
    if patch_owner is not None:
        if patch_owner not in AGENT_IDS:
            raise SwarmContractError(f"Invalid patch_owner: {patch_owner}")
        if patch_owner in {"A01", "A06", "A09", "A11"}:
            raise SwarmContractError(f"Independent gate/reviewer cannot be patch owner: {patch_owner}")
        if patch_owner == "A10" and not allow_coordinator_patch:
            raise SwarmContractError("A10 may patch only agent-governance infrastructure missions")
    write_scope = _string_list(plan.get("write_scope"), "plan.write_scope")
    if patch_owner is not None and not write_scope:
        raise SwarmContractError("A patch owner requires an explicit non-empty write_scope")
    if any(scope.startswith("/") or ".." in Path(scope).parts for scope in write_scope):
        raise SwarmContractError("write_scope must contain repository-relative prefixes")
    affected = _string_list(plan.get("affected_domains"), "plan.affected_domains")
    if not affected:
        raise SwarmContractError("plan.affected_domains must not be empty")
    return plan


def normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def path_in_scope(path: str, scopes: Iterable[str]) -> bool:
    normalized = normalize_repo_path(path)
    for raw_scope in scopes:
        scope = normalize_repo_path(raw_scope)
        if scope.endswith("/"):
            if normalized.startswith(scope):
                return True
        elif normalized == scope or normalized.startswith(scope + "/"):
            return True
    return False


def is_protected_live_path(path: str) -> bool:
    normalized = normalize_repo_path(path)
    return any(normalized.startswith(prefix) for prefix in PROTECTED_LIVE_PREFIXES)


def validate_patch_paths(
    changed_paths: Iterable[str], write_scope: Iterable[str], *, allow_live_release: bool
) -> tuple[str, ...]:
    paths = tuple(normalize_repo_path(path) for path in changed_paths)
    bad_scope = tuple(path for path in paths if not path_in_scope(path, write_scope))
    if bad_scope:
        raise SwarmContractError(f"Patch changed files outside A10 write_scope: {bad_scope}")
    protected = tuple(path for path in paths if is_protected_live_path(path))
    if protected and not allow_live_release:
        raise SwarmContractError(
            f"Ordinary swarm mission may not change live-order/release paths: {protected}"
        )
    return paths


def validate_report(
    report: dict[str, Any], *, agent_id: str, mission_id: str, round_no: int, phase: str
) -> dict[str, Any]:
    if report.get("agent_id") != agent_id:
        raise SwarmContractError(f"Report agent_id mismatch for {agent_id}")
    if report.get("mission_id") != mission_id:
        raise SwarmContractError(f"Report mission_id mismatch for {agent_id}")
    if report.get("round") != round_no:
        raise SwarmContractError(f"Report round mismatch for {agent_id}")
    if report.get("phase") != phase:
        raise SwarmContractError(f"Report phase mismatch for {agent_id}")
    verdict = report.get("verdict")
    if verdict not in REPORT_VERDICTS:
        raise SwarmContractError(f"Invalid verdict from {agent_id}: {verdict!r}")
    summary = report.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise SwarmContractError(f"Agent {agent_id} report requires a non-empty summary")
    for name in ("findings", "evidence", "next_actions"):
        _string_list(report.get(name), f"report.{name}")
    if verdict in {"PASS", "QA_PASS", "GOVERNANCE_PASS"} and not report.get("evidence"):
        raise SwarmContractError(f"Positive verdict from {agent_id} requires evidence")
    if agent_id == "A09" and verdict not in {"QA_PASS", "QA_FAIL", "BLOCKED"}:
        raise SwarmContractError("A09 must issue QA_PASS/QA_FAIL/BLOCKED")
    if agent_id == "A11" and phase == "governance" and verdict not in {
        "GOVERNANCE_PASS",
        "GOVERNANCE_FAIL",
        "BLOCKED",
    }:
        raise SwarmContractError(
            "A11 final governance phase must issue GOVERNANCE_PASS/GOVERNANCE_FAIL/BLOCKED"
        )
    return report


@dataclass(frozen=True)
class Completion:
    done: bool
    state: str
    reason: str


def completion_from_reports(
    mission: dict[str, Any], reports: dict[str, dict[str, Any]]
) -> Completion:
    required = required_agents(mission)
    qa = reports.get("A09")
    governance = reports.get("A11:governance") or reports.get("A11")
    if qa is None or qa.get("verdict") != "QA_PASS":
        return Completion(False, "REPAIR_LOOP", "A09 has not issued QA_PASS")
    if governance is None or governance.get("verdict") != "GOVERNANCE_PASS":
        return Completion(False, "REPAIR_LOOP", "A11 has not issued GOVERNANCE_PASS")
    for agent in required:
        if agent in {"A09", "A11"}:
            continue
        report = reports.get(agent)
        if report is None:
            return Completion(False, "REPAIR_LOOP", f"Missing required report from {agent}")
        if report.get("verdict") not in {"PASS", "NOT_APPLICABLE"}:
            return Completion(False, "REPAIR_LOOP", f"{agent} is not cleared")
    return Completion(True, "DONE", "QA_PASS + GOVERNANCE_PASS + all mandatory reports")


def new_runtime(mission: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mission_id": mission.get("id"),
        "run_id": run_id,
        "state": "PREFLIGHT",
        "round": 1,
        "created_at_utc": utc_now_text(),
        "updated_at_utc": utc_now_text(),
        "required_agents": list(required_agents(mission)),
        "agent_state": {
            agent: {
                "status": "PENDING",
                "attempt": 0,
                "last_heartbeat_utc": None,
                "last_verdict": None,
                "last_report": None,
            }
            for agent in required_agents(mission)
        },
        "history": [],
    }


def heartbeat(runtime: dict[str, Any], agent_id: str, status: str) -> None:
    states = runtime.get("agent_state")
    if not isinstance(states, dict) or agent_id not in states:
        raise SwarmContractError(f"Agent {agent_id} not present in runtime")
    state = states[agent_id]
    state["status"] = status
    state["last_heartbeat_utc"] = utc_now_text()
    runtime["updated_at_utc"] = utc_now_text()


def record_attempt(
    runtime: dict[str, Any], agent_id: str, *, verdict: str, report_path: str, note: str = ""
) -> None:
    states = runtime["agent_state"]
    state = states[agent_id]
    state["attempt"] = int(state.get("attempt") or 0) + 1
    state["status"] = "COMPLETED" if verdict not in {"FAIL", "QA_FAIL", "GOVERNANCE_FAIL", "BLOCKED"} else "FAILED"
    state["last_heartbeat_utc"] = utc_now_text()
    state["last_verdict"] = verdict
    state["last_report"] = report_path
    runtime.setdefault("history", []).append(
        {
            "at_utc": utc_now_text(),
            "agent_id": agent_id,
            "attempt": state["attempt"],
            "verdict": verdict,
            "report": report_path,
            "note": note,
        }
    )
    runtime["updated_at_utc"] = utc_now_text()


def reopen_round(runtime: dict[str, Any], *, reason: str) -> None:
    runtime["state"] = "REPAIR_LOOP"
    runtime.setdefault("history", []).append(
        {"at_utc": utc_now_text(), "event": "REOPEN", "reason": reason}
    )
    runtime["round"] = int(runtime.get("round") or 1) + 1
    for state in runtime["agent_state"].values():
        state["status"] = "PENDING"
        state["last_verdict"] = None
        state["last_report"] = None
    runtime["updated_at_utc"] = utc_now_text()


def mark_done(runtime: dict[str, Any]) -> None:
    runtime["state"] = "DONE"
    runtime["updated_at_utc"] = utc_now_text()
    runtime.setdefault("history", []).append(
        {"at_utc": utc_now_text(), "event": "DONE"}
    )


def agent_prompt_contract(
    *,
    agent_id: str,
    mission: dict[str, Any],
    round_no: int,
    phase: str,
    report_relpath: str,
    role_text: str,
    plan: dict[str, Any] | None,
) -> str:
    """Build the common immutable contract prepended to every Codex role prompt."""
    objective = str(mission.get("objective") or mission.get("title") or mission.get("id"))
    regressions = known_regression_requirements(mission)
    plan_text = json.dumps(plan or {}, indent=2, ensure_ascii=False)
    regression_text = json.dumps(regressions, indent=2, ensure_ascii=False)
    return f"""You are {agent_id} in the Hixton Engineering Swarm.

Read AGENTS.md and the persistent engineering maps in agent_memory before making claims.
Mission: {mission.get('id')} — {objective}
Round: {round_no}
Phase: {phase}
Role contract:\n{role_text}

A10 plan (empty only before planning):\n{plan_text}
Known regression obligations:\n{regression_text}

Safety and evidence rules:
- Never expose credentials, ignored operator data or account secrets.
- Never place a real Binance order and never weaken a live-release gate unless the taskboard explicitly contains allow_live_release=true from the owner.
- Historical profit is not correctness evidence. Distinguish code defect, data difference, state/path difference, intended model difference, research hypothesis and external unknown.
- Do not mark your own patch as released. A09 and A11 are independent gates.
- Your required machine-readable report path is exactly: {report_relpath}
- Write valid UTF-8 JSON there with fields: agent_id, mission_id, round, phase, verdict, summary, findings[], evidence[], next_actions[].
- Positive PASS-like verdicts require concrete evidence entries.
- If the mission is irrelevant to your specialty, still inspect its possible impact and use NOT_APPLICABLE with evidence explaining why.
"""

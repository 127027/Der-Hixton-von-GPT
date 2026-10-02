"""Cost-capped shadow orchestrator for the Hixton A01-A11 engineering swarm.

V1 is deliberately read-only. It consumes repository contracts and optional
agent evidence, then emits a deterministic routing plan. It performs no network
requests, model calls, GitHub writes, Binance actions, subprocess execution or
strategy activation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "agent_memory" / "swarm" / "registry.json"
DEFAULT_TASKBOARD = ROOT / "agent_memory" / "swarm" / "taskboard.json"
DEFAULT_POLICY = ROOT / "agent_memory" / "orchestrator" / "policy.json"
AGENT_IDS = tuple(f"A{i:02d}" for i in range(1, 12))
KNOWN_DETERMINISTIC_DEFECTS = {
    "SPECIALIST_OR_EVIDENCE_CONTRACT",
    "LIFECYCLE_OR_EVIDENCE_CONTRACT",
}


class OrchestratorContractError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OrchestratorContractError(f"cannot load JSON contract {path}: {error}") from error
    if not isinstance(value, dict):
        raise OrchestratorContractError(f"JSON contract must be an object: {path}")
    return value


def validate_contracts(
    registry: dict[str, Any],
    taskboard: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    agents = registry.get("agents")
    if not isinstance(agents, list):
        raise OrchestratorContractError("registry agents missing")
    ids = tuple(str(item.get("id")) for item in agents if isinstance(item, dict))
    if ids != AGENT_IDS:
        raise OrchestratorContractError(f"registry must contain exact A01-A11 order, got {ids!r}")

    active = taskboard.get("active_mission")
    if not isinstance(active, dict):
        raise OrchestratorContractError("active_mission missing")
    required = active.get("required_agents")
    if not isinstance(required, list) or set(map(str, required)) != set(AGENT_IDS):
        raise OrchestratorContractError("active mission must require exact A01-A11")

    if policy.get("mode") != "SHADOW_ONLY":
        raise OrchestratorContractError("V1 policy must remain SHADOW_ONLY")

    cost = policy.get("cost_policy")
    if not isinstance(cost, dict):
        raise OrchestratorContractError("cost_policy missing")
    if cost.get("default_ai_enabled") is not False:
        raise OrchestratorContractError("default AI must be disabled")
    if int(cost.get("default_max_ai_escalations_per_cycle", -1)) != 0:
        raise OrchestratorContractError("default AI budget must be zero")
    if cost.get("status_polling_may_use_ai") is not False:
        raise OrchestratorContractError("status polling may not spend AI budget")
    if cost.get("known_repairs_may_use_ai") is not False:
        raise OrchestratorContractError("known repairs may not spend AI budget")

    security = policy.get("security")
    if not isinstance(security, dict):
        raise OrchestratorContractError("security policy missing")
    forbidden_true = (
        "binance_private_credentials_allowed",
        "real_money_orders_allowed",
        "testnet_orders_allowed",
        "automatic_strategy_activation_allowed",
        "automatic_merge_allowed",
    )
    enabled = [key for key in forbidden_true if security.get(key) is not False]
    if enabled:
        raise OrchestratorContractError(f"unsafe orchestrator permissions enabled: {enabled}")

    gates = policy.get("independent_gates")
    if not isinstance(gates, dict):
        raise OrchestratorContractError("independent_gates missing")
    for gate in ("A09", "A11"):
        value = gates.get(gate)
        if not isinstance(value, dict):
            raise OrchestratorContractError(f"{gate} gate contract missing")
        if value.get("required") is not True:
            raise OrchestratorContractError(f"{gate} must remain required")
        if value.get("replaceable_by_master") is not False:
            raise OrchestratorContractError(f"{gate} may not be replaced by master")
        if value.get("ai_self_approval_allowed") is not False:
            raise OrchestratorContractError(f"{gate} may not self-approve through AI")

    roles = policy.get("roles")
    if not isinstance(roles, dict) or set(roles) != set(AGENT_IDS):
        raise OrchestratorContractError("policy roles must contain exact A01-A11")

    notes.append("A01-A11 registry preserved")
    notes.append("A09 QA and A11 governance remain independent")
    notes.append("default AI budget is zero")
    notes.append("cloud remains Binance-key-free and order-free")
    return notes


def _report_priority(report: dict[str, Any]) -> tuple[int, str]:
    scope = str(report.get("audit_scope", ""))
    scope_rank = {"full": 3, "parallel-full": 3, "base": 2}.get(scope, 1)
    return (scope_rank, str(report.get("finished_at_utc", "")))


def load_reports(directory: Path | None) -> dict[str, dict[str, Any]]:
    if directory is None or not directory.exists():
        return {}
    selected: dict[str, dict[str, Any]] = {}
    for path in directory.rglob("*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(report, dict):
            continue
        agent = str(report.get("agent", ""))
        if agent not in AGENT_IDS:
            continue
        current = selected.get(agent)
        if current is None or _report_priority(report) > _report_priority(current):
            selected[agent] = report
    return selected


def _role_mode(policy: dict[str, Any], role: str) -> str:
    roles = policy.get("roles", {})
    value = roles.get(role, {}) if isinstance(roles, dict) else {}
    return str(value.get("mode", "DETERMINISTIC_FIRST"))


def _unknown_failure(report: dict[str, Any]) -> bool:
    if report.get("verdict") != "FAIL":
        return False
    if report.get("repair_routes"):
        return False
    if report.get("defect_class") in KNOWN_DETERMINISTIC_DEFECTS:
        return False
    return True


def build_plan(
    registry: dict[str, Any],
    taskboard: dict[str, Any],
    policy: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    *,
    allow_ai: bool = False,
    max_ai_escalations: int = 0,
) -> dict[str, Any]:
    contract_notes = validate_contracts(registry, taskboard, policy)
    active = taskboard["active_mission"]
    required = [str(value) for value in active["required_agents"]]
    cost = policy["cost_policy"]
    hard_max = int(cost["hard_max_ai_escalations_per_cycle"])
    requested_budget = max(0, int(max_ai_escalations))
    authorized_budget = min(requested_budget, hard_max) if allow_ai else 0

    work_items: list[dict[str, Any]] = []
    ai_candidates: list[str] = []
    for role in required:
        report = reports.get(role)
        mode = _role_mode(policy, role)
        if report is None:
            work_items.append(
                {
                    "role": role,
                    "action": "RERUN_DETERMINISTIC",
                    "reason": "missing_report",
                    "cost_class": "NO_LLM",
                }
            )
            continue

        verdict = str(report.get("verdict", ""))
        if verdict == "PASS":
            continue

        if role in {"A09", "A11"} or mode == "DETERMINISTIC_ONLY" or not _unknown_failure(report):
            work_items.append(
                {
                    "role": role,
                    "action": "REPAIR_OR_RERUN_DETERMINISTIC_FIRST",
                    "reason": str(report.get("defect_class") or report.get("error") or "failed_duty"),
                    "cost_class": "NO_LLM",
                }
            )
            continue

        ai_candidates.append(role)
        work_items.append(
            {
                "role": role,
                "action": "AI_ESCALATION_CANDIDATE" if authorized_budget > 0 else "DETERMINISTIC_DIAGNOSIS_THEN_OWNER_REVIEW",
                "reason": str(report.get("error") or "unknown_failure"),
                "cost_class": "CAPPED_LLM" if authorized_budget > 0 else "NO_LLM",
            }
        )

    qa = reports.get("A09", {})
    governance = reports.get("A11", {})
    all_pass = all(reports.get(role, {}).get("verdict") == "PASS" for role in required)
    gates_green = qa.get("gate") == "QA_PASS" and governance.get("gate") == "GOVERNANCE_PASS"
    if all_pass and gates_green:
        overall = "GREEN_NO_ACTION"
    elif all_pass:
        overall = "GATE_INCOMPLETE"
    else:
        overall = "REPAIR_REQUIRED"

    return {
        "schema_version": 1,
        "mode": "SHADOW_ONLY",
        "mission_id": active.get("id"),
        "mission_state": active.get("state"),
        "overall": overall,
        "authoritative_release_path": "A01-A11_GITHUB_ACTIONS",
        "mutations_performed": False,
        "model_calls_performed": 0,
        "contract_notes": contract_notes,
        "reports_seen": sorted(reports),
        "work_items": work_items,
        "ai_budget": {
            "default_enabled": bool(cost["default_ai_enabled"]),
            "requested_unlock": bool(allow_ai),
            "requested_max_escalations": requested_budget,
            "authorized_max_escalations": authorized_budget,
            "candidate_roles": ai_candidates,
            "calls_performed": 0,
        },
        "protected_gates": {
            "A09_required": True,
            "A11_required": True,
            "master_may_self_approve": False,
        },
        "security": policy["security"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--taskboard", type=Path, default=DEFAULT_TASKBOARD)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--reports-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-ai", action="store_true")
    parser.add_argument("--max-ai-escalations", type=int, default=0)
    args = parser.parse_args(argv)

    plan = build_plan(
        load_json(args.registry),
        load_json(args.taskboard),
        load_json(args.policy),
        load_reports(args.reports_dir),
        allow_ai=args.allow_ai,
        max_ai_escalations=args.max_ai_escalations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

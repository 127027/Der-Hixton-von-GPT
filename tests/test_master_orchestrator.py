from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.master_orchestrator import AGENT_IDS, build_plan, load_json, validate_contracts

ROOT = Path(__file__).resolve().parents[1]


class MasterOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_json(ROOT / "agent_memory" / "swarm" / "registry.json")
        self.taskboard = load_json(ROOT / "agent_memory" / "swarm" / "taskboard.json")
        self.policy = load_json(ROOT / "agent_memory" / "orchestrator" / "policy.json")

    def test_contract_keeps_zero_cost_default_and_independent_gates(self) -> None:
        notes = validate_contracts(self.registry, self.taskboard, self.policy)
        self.assertIn("default AI budget is zero", notes)
        self.assertFalse(self.policy["cost_policy"]["default_ai_enabled"])
        self.assertEqual(self.policy["cost_policy"]["default_max_ai_escalations_per_cycle"], 0)
        self.assertFalse(self.policy["independent_gates"]["A09"]["replaceable_by_master"])
        self.assertFalse(self.policy["independent_gates"]["A11"]["replaceable_by_master"])

    def test_missing_reports_are_routed_without_ai(self) -> None:
        plan = build_plan(self.registry, self.taskboard, self.policy, {})
        self.assertEqual(plan["overall"], "REPAIR_REQUIRED")
        self.assertEqual(len(plan["work_items"]), 11)
        self.assertTrue(all(item["cost_class"] == "NO_LLM" for item in plan["work_items"]))
        self.assertEqual(plan["ai_budget"]["authorized_max_escalations"], 0)
        self.assertEqual(plan["model_calls_performed"], 0)

    def test_green_chain_requires_both_qa_and_governance_gates(self) -> None:
        reports = {role: {"agent": role, "verdict": "PASS"} for role in AGENT_IDS}
        reports["A09"]["gate"] = "QA_PASS"
        reports["A11"]["gate"] = "GOVERNANCE_PASS"
        plan = build_plan(self.registry, self.taskboard, self.policy, reports)
        self.assertEqual(plan["overall"], "GREEN_NO_ACTION")
        self.assertEqual(plan["work_items"], [])

        reports["A11"].pop("gate")
        plan = build_plan(self.registry, self.taskboard, self.policy, reports)
        self.assertEqual(plan["overall"], "GATE_INCOMPLETE")

    def test_unknown_failure_cannot_spend_ai_without_explicit_unlock(self) -> None:
        reports = {role: {"agent": role, "verdict": "PASS"} for role in AGENT_IDS}
        reports["A02"] = {
            "agent": "A02",
            "verdict": "FAIL",
            "error": "unclassified research implementation defect",
        }
        locked = build_plan(
            self.registry,
            self.taskboard,
            self.policy,
            reports,
            allow_ai=False,
            max_ai_escalations=2,
        )
        a02 = next(item for item in locked["work_items"] if item["role"] == "A02")
        self.assertEqual(a02["action"], "DETERMINISTIC_DIAGNOSIS_THEN_OWNER_REVIEW")
        self.assertEqual(a02["cost_class"], "NO_LLM")
        self.assertEqual(locked["ai_budget"]["authorized_max_escalations"], 0)

        unlocked = build_plan(
            self.registry,
            self.taskboard,
            self.policy,
            reports,
            allow_ai=True,
            max_ai_escalations=1,
        )
        a02 = next(item for item in unlocked["work_items"] if item["role"] == "A02")
        self.assertEqual(a02["action"], "AI_ESCALATION_CANDIDATE")
        self.assertEqual(a02["cost_class"], "CAPPED_LLM")
        self.assertEqual(unlocked["ai_budget"]["authorized_max_escalations"], 1)
        self.assertEqual(unlocked["model_calls_performed"], 0)

    def test_security_contract_is_order_free(self) -> None:
        security = self.policy["security"]
        self.assertFalse(security["binance_private_credentials_allowed"])
        self.assertFalse(security["real_money_orders_allowed"])
        self.assertFalse(security["testnet_orders_allowed"])
        self.assertFalse(security["automatic_strategy_activation_allowed"])
        self.assertFalse(security["automatic_merge_allowed"])


if __name__ == "__main__":
    unittest.main()

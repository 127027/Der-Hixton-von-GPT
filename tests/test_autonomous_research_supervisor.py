from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.autonomous_research_supervisor import build_decision, load_json

ROOT = Path(__file__).resolve().parents[1]


class AutonomousResearchSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        policy = load_json(ROOT / "agent_memory" / "autonomy" / "policy.json")
        assert policy is not None
        self.policy = policy

    def test_no_evidence_means_continue_not_stop(self) -> None:
        result = build_decision(self.policy, None, None)
        self.assertEqual(result["action"], "CONTINUE_RESEARCH")
        self.assertEqual(result["model_calls_required_for_this_decision"], 0)

    def test_coin_candidate_requires_cross_window_before_patch(self) -> None:
        coin = {
            "aggregate_promotion_gate": {"promotable": True},
            "profile_parity": {"current_match": True, "candidate_match": True},
            "per_coin": {"BTCUSDC": {"accepted": True}},
        }
        result = build_decision(self.policy, coin, None)
        self.assertEqual(result["action"], "RUN_CROSS_WINDOW_ROBUSTNESS")
        promoted = build_decision(
            self.policy,
            coin,
            None,
            cross_window={"candidate": "ranked_repeat:4x62.50", "cross_window_pass": True},
        )
        self.assertEqual(promoted["action"], "RUN_CROSS_WINDOW_ROBUSTNESS")
        self.assertEqual(promoted["validated_candidates"], [])

    def test_more_trades_alone_is_not_enough(self) -> None:
        layout = {
            "frequency_comparison": {
                "strict_frequency_improvements": []
            }
        }
        result = build_decision(self.policy, None, layout)
        self.assertEqual(result["action"], "CONTINUE_RESEARCH")

    def test_strict_layout_candidate_requires_robustness(self) -> None:
        layout = {
            "frequency_comparison": {
                "strict_frequency_improvements": ["one_per_symbol:3x83.33"]
            }
        }
        result = build_decision(self.policy, None, layout)
        self.assertEqual(result["action"], "RUN_CROSS_WINDOW_ROBUSTNESS")
        cross_only = build_decision(
            self.policy,
            None,
            layout,
            cross_window={
                "candidate": "one_per_symbol:3x83.33",
                "cross_window_pass": True,
            },
        )
        self.assertEqual(cross_only["action"], "RUN_CROSS_WINDOW_ROBUSTNESS")
        validated = build_decision(
            self.policy,
            None,
            layout,
            cross_window={
                "candidate": "one_per_symbol:3x83.33",
                "cross_window_pass": True,
            },
            shifted_window={
                "layout": {
                    "candidate": "one_per_symbol:3x83.33",
                    "shifted_window_pass": True,
                },
                "coin_profile": {
                    "accepted_symbols": [],
                    "shifted_window_pass": False,
                },
            },
            red_team={
                "capital_layout": {
                    "candidate": "one_per_symbol:3x83.33",
                    "pass": True,
                },
                "coin_profile": {"accepted_symbols": [], "pass": False},
            },
        )
        self.assertEqual(
            validated["action"], "BUILD_ENGINEERING_CANDIDATE_AND_RUN_A01_A11"
        )

    def test_coin_candidate_can_only_validate_with_matching_shifted_evidence(self) -> None:
        coin = {
            "aggregate_promotion_gate": {"promotable": True},
            "profile_parity": {"current_match": True, "candidate_match": True},
            "per_coin": {"AVAXUSDC": {"accepted": True}},
        }
        wrong = build_decision(
            self.policy,
            coin,
            None,
            shifted_window={
                "layout": {"candidate": None, "shifted_window_pass": False},
                "coin_profile": {
                    "accepted_symbols": ["DOGEUSDC"],
                    "shifted_window_pass": True,
                },
            },
        )
        self.assertEqual(wrong["action"], "RUN_CROSS_WINDOW_ROBUSTNESS")
        good = build_decision(
            self.policy,
            coin,
            None,
            shifted_window={
                "layout": {"candidate": None, "shifted_window_pass": False},
                "coin_profile": {
                    "accepted_symbols": ["AVAXUSDC"],
                    "shifted_window_pass": True,
                },
            },
            red_team={
                "capital_layout": {"candidate": None, "pass": False},
                "coin_profile": {
                    "accepted_symbols": ["AVAXUSDC"],
                    "pass": True,
                },
            },
        )
        self.assertEqual(good["action"], "BUILD_ENGINEERING_CANDIDATE_AND_RUN_A01_A11")

    def test_red_team_is_mandatory_even_after_shifted_pass(self) -> None:
        coin = {
            "aggregate_promotion_gate": {"promotable": True},
            "profile_parity": {"current_match": True, "candidate_match": True},
            "per_coin": {"AVAXUSDC": {"accepted": True}},
        }
        result = build_decision(
            self.policy,
            coin,
            None,
            shifted_window={
                "coin_profile": {
                    "accepted_symbols": ["AVAXUSDC"],
                    "shifted_window_pass": True,
                }
            },
        )
        self.assertEqual(result["action"], "RUN_CROSS_WINDOW_ROBUSTNESS")

    def test_real_money_activation_remains_forbidden(self) -> None:
        result = build_decision(self.policy, None, None)
        self.assertFalse(result["paper_auto_activate"])
        self.assertFalse(result["live_auto_activate"])
        self.assertFalse(result["real_money_orders_allowed"])


if __name__ == "__main__":
    unittest.main()

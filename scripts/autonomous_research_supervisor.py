"""Deterministic supervisor for Hixton continuous research.

This layer does not place orders or mutate strategy/runtime state. It evaluates
research evidence and decides whether to keep researching, request cross-window
robustness, or nominate a candidate for the exact-head A01-A11 promotion path.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal as D
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "agent_memory" / "autonomy" / "policy.json"


class ResearchContractError(RuntimeError):
    pass


def load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ResearchContractError(f"{path} must contain a JSON object")
    return value


def _coin_signal(evidence: dict[str, Any] | None) -> dict[str, Any]:
    if not evidence:
        return {"available": False, "promotable": False, "reason": "missing_coin_evidence"}
    gate = evidence.get("aggregate_promotion_gate")
    parity = evidence.get("profile_parity")
    promotable = bool(isinstance(gate, dict) and gate.get("promotable") is True)
    parity_ok = bool(
        isinstance(parity, dict)
        and parity.get("current_match") is True
        and parity.get("candidate_match") is True
    )
    per_coin = evidence.get("per_coin")
    accepted = []
    if isinstance(per_coin, dict):
        accepted = sorted(
            str(symbol)
            for symbol, row in per_coin.items()
            if isinstance(row, dict) and row.get("accepted") is True
        )
    return {
        "available": True,
        "promotable": promotable and parity_ok and bool(accepted),
        "aggregate_gate": promotable,
        "profile_parity": parity_ok,
        "accepted_symbols": accepted,
        "reason": (
            "candidate_needs_cross_window_confirmation"
            if promotable and parity_ok and accepted
            else "no_strict_coin_candidate"
        ),
    }


def _layout_signal(evidence: dict[str, Any] | None) -> dict[str, Any]:
    if not evidence:
        return {"available": False, "promotable": False, "reason": "missing_layout_evidence"}
    comparison = evidence.get("frequency_comparison")
    strict: list[str] = []
    if isinstance(comparison, dict):
        raw = comparison.get("strict_frequency_improvements")
        if isinstance(raw, list):
            strict = [str(value) for value in raw]
    return {
        "available": True,
        "promotable": bool(strict),
        "strict_frequency_improvements": strict,
        "reason": (
            "candidate_needs_cross_window_confirmation"
            if strict
            else "no_layout_candidate_improves_trades_without_equity_regression"
        ),
    }


def build_decision(
    policy: dict[str, Any],
    coin: dict[str, Any] | None,
    layout: dict[str, Any] | None,
    *,
    cross_window: dict[str, Any] | None = None,
    shifted_window: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if policy.get("mode") != "AUTONOMOUS_RESEARCH_AND_ENGINEERING":
        raise ResearchContractError("autonomy policy mode mismatch")

    coin_signal = _coin_signal(coin)
    layout_signal = _layout_signal(layout)
    candidates = []
    if coin_signal["promotable"]:
        candidates.append({"type": "COIN_PROFILE", **coin_signal})
    if layout_signal["promotable"]:
        candidates.append({"type": "CAPITAL_LAYOUT", **layout_signal})

    validated: list[dict[str, Any]] = []
    pending_robustness: list[dict[str, Any]] = []
    cross_layout = None
    cross_ok = False
    if isinstance(cross_window, dict):
        cross_layout = cross_window.get("candidate")
        cross_ok = cross_window.get("cross_window_pass") is True

    shifted_layout = {}
    shifted_coin = {}
    if isinstance(shifted_window, dict):
        raw_layout = shifted_window.get("layout")
        raw_coin = shifted_window.get("coin_profile")
        shifted_layout = raw_layout if isinstance(raw_layout, dict) else {}
        shifted_coin = raw_coin if isinstance(raw_coin, dict) else {}

    for candidate in candidates:
        if candidate["type"] == "CAPITAL_LAYOUT":
            strict = candidate.get("strict_frequency_improvements", [])
            layout_key = shifted_layout.get("candidate")
            if (
                cross_ok
                and cross_layout in strict
                and shifted_layout.get("shifted_window_pass") is True
                and layout_key in strict
            ):
                validated.append(candidate)
            else:
                pending_robustness.append(candidate)
            continue

        if candidate["type"] == "COIN_PROFILE":
            expected = set(candidate.get("accepted_symbols", []))
            observed = set(shifted_coin.get("accepted_symbols", []))
            if (
                shifted_coin.get("shifted_window_pass") is True
                and expected
                and expected == observed
            ):
                validated.append(candidate)
            else:
                pending_robustness.append(candidate)
            continue

        pending_robustness.append(candidate)

    if not candidates:
        action = "CONTINUE_RESEARCH"
        next_focus = [
            "reduce avoidable NO_FREE_SLOT while preserving baseline/stress profit",
            "expand per-coin valid opportunities using winner/loss cluster evidence",
            "test exit/holding-time changes separately from entry changes",
        ]
    elif validated:
        action = "BUILD_ENGINEERING_CANDIDATE_AND_RUN_A01_A11"
        next_focus = ["exact-head patch for validated candidate, full regression, QA_PASS, GOVERNANCE_PASS"]
    else:
        action = "RUN_CROSS_WINDOW_ROBUSTNESS"
        next_focus = ["confirm each candidate type with its own independent robustness evidence"]

    return {
        "schema_version": 1,
        "mode": policy["mode"],
        "action": action,
        "candidates": candidates,
        "validated_candidates": validated,
        "pending_robustness": pending_robustness,
        "next_focus": next_focus,
        "anti_overfit_required": True,
        "engineering_auto_apply_allowed_after_gates": bool(
            policy.get("promotion", {}).get("engineering_auto_apply_allowed")
        ),
        "paper_auto_activate": False,
        "live_auto_activate": False,
        "real_money_orders_allowed": False,
        "model_calls_required_for_this_decision": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--coin-evidence", type=Path)
    parser.add_argument("--layout-evidence", type=Path)
    parser.add_argument("--cross-window-evidence", type=Path)
    parser.add_argument("--shifted-window-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    policy = load_json(args.policy)
    if policy is None:
        raise ResearchContractError("policy missing")
    decision = build_decision(
        policy,
        load_json(args.coin_evidence),
        load_json(args.layout_evidence),
        cross_window=load_json(args.cross_window_evidence),
        shifted_window=load_json(args.shifted_window_evidence),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

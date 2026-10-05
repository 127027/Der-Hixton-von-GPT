"""Persist one autonomous adaptive Satellite round and prepare the next.

This script runs only after the evidence artifact has been produced. It never uses
validation evidence to choose the next TRAINING seed: the seed always comes from the
current round's training winner. Validation may only accept/reject promotion of the
separate reference benchmark.

If work remains, the workflow persists the next hypothesis as ready state only.
A later quarter-hour controller tick owns the next substantive launch; completion
of this script must never self-dispatch another research run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONTROL = Path("agent_memory/autonomy/satellite_adaptive_control.json")
STATE = Path("agent_memory/autonomy/satellite_adaptive_state.json")
MISSION = Path("agent_memory/autonomy/current_mission.json")
HEARTBEAT = Path("agent_memory/autonomy/heartbeat.json")
LOCK = Path("agent_memory/autonomy/research_build_lock.json")
HISTORY = Path("agent_memory/autonomy/satellite_run_delta_history.json")
LATEST = Path("agent_memory/autonomy/satellite_run_delta_latest.json")
HANDOFF = Path("agent_memory/autonomy/satellite_adaptive_handoff.json")
QSTATE = Path("agent_memory/autonomy/quarter_hour_state.json")
EVIDENCE = Path("evidence/satellite-isolated-5x250-adaptive-cycle.json")
MARKDOWN = Path("evidence/satellite-adaptive-run-delta.md")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _problem(row: dict, state_row: dict) -> str:
    if bool(state_row.get("reference_maturity_pass")):
        return "MATURE"
    if bool(state_row.get("reference_profitability_pass")):
        return "FREQUENCY_OR_EFFICIENCY_GAP"
    if row.get("profitability_pass"):
        return "REFERENCE_UPGRADE_PENDING"
    return "VALIDATION_GENERALIZATION_GAP"


def main() -> None:
    if LOCK.exists() and bool(_read(LOCK).get("locked", False)):
        raise RuntimeError("adaptive autocontinue forbidden while build lock is active")

    result = _read(EVIDENCE)
    control = _read(CONTROL)
    state = _read(STATE)
    mission = _read(MISSION)
    heartbeat = _read(HEARTBEAT)
    history = _read(HISTORY) if HISTORY.exists() else {"schema_version": 1, "records": []}
    qstate = _read(QSTATE) if QSTATE.exists() else {"schema_version": 1}

    round_no = int(result["round"])
    if round_no != int(control["round"]):
        raise RuntimeError(
            f"adaptive round mismatch evidence={round_no} control={control['round']}"
        )
    if result["study"] != "SATELLITE_ISOLATED_5X250_ADAPTIVE_CYCLE":
        raise RuntimeError(f"unexpected evidence study {result['study']!r}")

    run_number = int(os.environ.get("GITHUB_RUN_NUMBER", "0") or 0)
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    head_sha = os.environ.get("GITHUB_SHA", "")

    delta_rows: dict[str, dict] = {}
    accepted: list[str] = []

    for symbol, evidence_row in result["per_symbol"].items():
        state_row = state["per_symbol"][symbol]

        # Search direction is TRAINING-only. This happens regardless of validation.
        winner = evidence_row.get("training_winner")
        if winner and winner.get("candidate"):
            candidate = dict(winner["candidate"])
            candidate["name"] = (
                f"AUTO_R{round_no}_{candidate.get('name', 'TRAINING_WINNER')}"
            )
            state_row["training_seed"] = candidate
            state_row["training_seed_source_run"] = run_number
            state_row["training_seed_source_round"] = round_no
            state_row["training_seed_selection_mode"] = evidence_row.get("selection_mode")

        classification = str(evidence_row.get("classification", "UNCHANGED"))
        delta = evidence_row.get("economic_delta_vs_reference") or {}

        # Validation is rejection-only: it can permit a reference replacement,
        # but it never chooses the next training seed above.
        if classification == "IMPROVED" and delta.get("candidate_reference"):
            state_row["reference"] = delta["candidate_reference"]
            state_row["reference_source_run"] = run_number
            state_row["reference_source_round"] = round_no
            state_row["reference_profitability_pass"] = bool(
                delta.get("candidate_profitability_pass", False)
            )
            state_row["reference_maturity_pass"] = bool(
                delta.get("candidate_maturity_pass", False)
            )
            if state_row["reference_maturity_pass"]:
                state_row["reference_status"] = "FROZEN_MATURE_INCUMBENT"
            elif state_row["reference_profitability_pass"]:
                state_row["reference_status"] = "VALIDATED_INCUMBENT"
            else:
                state_row["reference_status"] = "RESEARCH_BENCHMARK"
            accepted.append(symbol)

        delta_rows[symbol] = {
            "classification": classification,
            "reason": evidence_row.get("reason"),
            "problem_after_round": _problem(evidence_row, state_row),
            "training_winner": (
                winner.get("candidate", {}).get("name") if winner else None
            ),
            "selection_mode": evidence_row.get("selection_mode"),
            "profitability_pass": evidence_row.get("profitability_pass"),
            "maturity_pass": evidence_row.get("maturity_pass"),
            "economic_delta_vs_reference": delta or None,
            "accepted_as_new_reference": symbol in accepted,
            "reference_source_run_after": state_row.get("reference_source_run"),
            "reference_maturity_after": bool(
                state_row.get("reference_maturity_pass", False)
            ),
        }

    mature_symbols = [
        symbol
        for symbol, row in state["per_symbol"].items()
        if bool(row.get("reference_maturity_pass", False))
    ]
    max_rounds = int(control["max_rounds"])
    family = str(result["family"])

    if len(mature_symbols) == len(state["per_symbol"]):
        control["status"] = "ALL_FIVE_MATURE"
        control["last_completed_round"] = round_no
        next_stage = "SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY"
        dispatch_next = False
        next_reason = "all five references are mature; build/verify shared idle replay bridge"
    else:
        # Family-registry exhaustion is a transition, never a terminal state.
        # Rounds beyond max_rounds are produced by the bounded TRAINING-only
        # point-in-time interaction generator in satellite_isolated_5x250_adaptive_cycle.
        control["round"] = round_no + 1
        control["status"] = "CONTINUE_GENERATED_CAUSAL_FAMILY"
        control["last_completed_round"] = round_no
        if round_no >= max_rounds:
            control["max_rounds"] = round_no + 1
        next_stage = "SATELLITE_ISOLATED_5X250_ADAPTIVE_CYCLE"
        # Persist the next hypothesis, but never chain-run immediately.
        # The next quarter-hour controller tick is analysis-only; only a later
        # quarter-hour tick may launch the prepared round.
        dispatch_next = False
        next_reason = (
            f"round {round_no} evaluated; next round {round_no + 1} prepared. "
            "NEEDS_ANALYSIS at the next quarter-hour tick; immediate self-dispatch is forbidden."
        )

    mission["current_stage"] = next_stage
    if isinstance(mission.get("satellite_layer"), dict):
        mission["satellite_layer"]["current_stage"] = next_stage
    recent = mission.setdefault("recent_evidence", {})
    recent[f"adaptive_round_{round_no}"] = {
        "run_number": run_number,
        "run_id": run_id,
        "family": family,
        "economic_progress": bool(result.get("economic_progress")),
        "improved_symbols": list(result.get("improved_symbols") or []),
        "accepted_reference_updates": accepted,
        "mature_symbols_after": mature_symbols,
        "per_symbol": delta_rows,
    }
    recent["next"] = next_reason

    heartbeat["sequence"] = int(heartbeat.get("sequence", 0)) + 1
    heartbeat["reason"] = next_reason
    heartbeat["target_stage"] = next_stage
    heartbeat["last_completed_adaptive_round"] = round_no
    heartbeat["last_completed_research_run"] = run_number

    record = {
        "run_number": run_number,
        "run_id": run_id,
        "head_sha": head_sha,
        "adaptive_round": round_no,
        "family": family,
        "technical_success": True,
        "economic_progress": bool(result.get("economic_progress")),
        "improved_symbols": list(result.get("improved_symbols") or []),
        "accepted_reference_updates": accepted,
        "mature_symbols_after": mature_symbols,
        "per_symbol": delta_rows,
        "patch_complete": True,
        "orchestration_phase": "NEEDS_ANALYSIS",
        "earliest_launch_policy": "ANALYSIS_TICK_THEN_LATER_LAUNCH_TICK",
        "next_stage": next_stage,
        "dispatch_next": dispatch_next,
        "next_reason": next_reason,
    }
    history.setdefault("records", []).append(record)

    handoff = {
        "schema_version": 1,
        "completed_run_number": run_number,
        "completed_run_id": run_id,
        "completed_round": round_no,
        "completed_family": family,
        "economic_progress": bool(result.get("economic_progress")),
        "accepted_reference_updates": accepted,
        "mature_symbols_after": mature_symbols,
        "next_stage": next_stage,
        "next_round": control.get("round"),
        "orchestration_phase": "NEEDS_ANALYSIS",
        "earliest_launch_policy": "ANALYSIS_TICK_THEN_LATER_LAUNCH_TICK",
        "dispatch_next": dispatch_next,
        "reason": next_reason,
    }

    qstate.update({
        "schema_version": 1,
        "phase": "NEEDS_ANALYSIS",
        "completed_run_number": run_number,
        "completed_run_id": run_id,
        "completed_round": round_no,
        "completed_family": family,
        "next_round": control.get("round"),
        "next_stage": next_stage,
        "economic_progress": bool(result.get("economic_progress")),
        "ready_for_dispatch": False,
        "last_transition_source": "research_completion",
    })

    _write(STATE, state)
    _write(CONTROL, control)
    _write(MISSION, mission)
    _write(HEARTBEAT, heartbeat)
    _write(HISTORY, history)
    _write(LATEST, record)
    _write(HANDOFF, handoff)
    _write(QSTATE, qstate)

    lines = [
        f"## RUN DELTA — #{run_number} / adaptive round {round_no}",
        "",
        f"- Family: **{family}**",
        f"- Technical result: **SUCCESS**",
        f"- Economic progress: **{str(bool(result.get('economic_progress'))).upper()}**",
        f"- Accepted reference updates: {', '.join(accepted) if accepted else 'none'}",
        f"- Mature references after run: {', '.join(mature_symbols) if mature_symbols else 'none'}",
        "",
        "| Symbol | Class | Problem after run | Training winner | Reference update |",
        "|---|---|---|---|---|",
    ]
    for symbol, row in delta_rows.items():
        lines.append(
            f"| {symbol} | {row['classification']} | {row['problem_after_round']} | "
            f"{row['training_winner'] or '-'} | "
            f"{'yes' if row['accepted_as_new_reference'] else 'no'} |"
        )
    lines += [
        "",
        f"- Patch complete: **YES**",
        f"- Next stage: **{next_stage}**",
        f"- Auto-dispatch next run: **{str(dispatch_next).upper()}**",
        f"- Reason: {next_reason}",
        "",
        "Training selects the next seed. Direct-USDC/validation remains rejection-only.",
        "Protected Core is not modified by this handoff.",
    ]
    MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(handoff, indent=2))


if __name__ == "__main__":
    main()

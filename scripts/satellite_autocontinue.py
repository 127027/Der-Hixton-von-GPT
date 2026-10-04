"""Persist a bounded training-only Satellite handoff for the next GitHub run.

This script never invents a new strategy from validation data. It only:
- advances the predeclared autonomous round counter;
- carries forward each symbol's TRAINING winner as the next round seed;
- records validation only as evidence;
- changes mission stage to a predeclared terminal/next stage when appropriate.

The workflow commits these control-file changes only after the current evidence
artifact has already been uploaded, which creates the next research run by push.
"""

from __future__ import annotations

import json
from pathlib import Path

MISSION = Path("agent_memory/autonomy/current_mission.json")
SEEDS = Path("agent_memory/autonomy/satellite_holding_seeds.json")
CONTROL = Path("agent_memory/autonomy/satellite_holding_control.json")
HEARTBEAT = Path("agent_memory/autonomy/heartbeat.json")
LOCK = Path("agent_memory/autonomy/research_build_lock.json")
EVIDENCE = Path("evidence/satellite-isolated-5x250-holding-refinement.json")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if LOCK.exists() and bool(_read(LOCK).get("locked", False)):
        raise RuntimeError("autocontinue forbidden while research build lock is active")

    result = _read(EVIDENCE)
    control = _read(CONTROL)
    seeds = _read(SEEDS)
    mission = _read(MISSION)
    heartbeat = _read(HEARTBEAT)

    round_no = int(result["round"])
    if round_no != int(control["round"]):
        raise RuntimeError(
            f"round mismatch evidence={round_no} control={control['round']}"
        )

    # TRAINING winners alone may steer the next round.
    for symbol, row in result["per_symbol"].items():
        winner = row.get("training_winner")
        if not winner:
            continue
        seeds["per_symbol"][symbol]["base_policy"] = winner["policy"]
        seeds["per_symbol"][symbol]["incumbent_source"] = (
            f"AUTO_HOLDING_ROUND_{round_no}_TRAINING_WINNER_{winner['name']}"
        )

    mature = list(result.get("mature_symbols") or [])
    next_stage = str(result["next_stage"])
    max_rounds = int(control["max_rounds"])

    if len(mature) == int(result["target_count"]):
        control["status"] = "ALL_FIVE_MATURE"
        control["completed_round"] = round_no
        mission["current_stage"] = "SATELLITE_FIVE_MATURE_SHARED_IDLE_REPLAY"
        mission["satellite_layer"]["current_stage"] = mission["current_stage"]
        reason = "all five Satellite profiles reached the bounded maturity contract"
    elif round_no < max_rounds:
        control["round"] = round_no + 1
        control["status"] = "CONTINUE"
        control["last_completed_round"] = round_no
        mission["current_stage"] = "SATELLITE_ISOLATED_5X250_HOLDING_REFINEMENT"
        mission["satellite_layer"]["current_stage"] = mission["current_stage"]
        reason = f"advance autonomous Satellite holding refinement to round {round_no + 1}"
    else:
        control["status"] = "BOUNDED_ROUNDS_EXHAUSTED_NEEDS_NEW_CAUSAL_FAMILY"
        control["last_completed_round"] = round_no
        mission["current_stage"] = "SATELLITE_ISOLATED_5X250_NEEDS_NEW_CAUSAL_FAMILY"
        mission["satellite_layer"]["current_stage"] = mission["current_stage"]
        reason = "bounded holding rounds exhausted; controller must derive a new training-led causal family"

    recent = mission.setdefault("recent_evidence", {})
    recent[f"auto_holding_round_{round_no}"] = {
        "mature_symbols": mature,
        "profitability_pass_symbols": list(result.get("profitability_pass_symbols") or []),
        "next_stage": next_stage,
        "per_symbol": {
            symbol: {
                "training_winner": (
                    row.get("training_winner", {}).get("name")
                    if row.get("training_winner")
                    else None
                ),
                "profitability_pass": bool(row.get("profitability_pass", False)),
                "maturity_pass": bool(row.get("maturity_pass", False)),
                "full_3y_stress_net_pnl": (
                    row.get("validation", {})
                    .get("full_3y_proxy_stress", {})
                    .get("net_pnl")
                    if row.get("validation")
                    else None
                ),
                "full_3y_stress_completed_trades": (
                    row.get("validation", {})
                    .get("full_3y_proxy_stress", {})
                    .get("completed_trades")
                    if row.get("validation")
                    else None
                ),
                "validation_stress_net_pnl": (
                    row.get("validation", {}).get("stress", {}).get("net_pnl")
                    if row.get("validation")
                    else None
                ),
            }
            for symbol, row in result["per_symbol"].items()
        },
    }
    recent["next"] = reason

    heartbeat["sequence"] = int(heartbeat.get("sequence", 0)) + 1
    heartbeat["reason"] = reason
    heartbeat["target_stage"] = mission["current_stage"]
    heartbeat["last_completed_autonomous_round"] = round_no

    _write(SEEDS, seeds)
    _write(CONTROL, control)
    _write(MISSION, mission)
    _write(HEARTBEAT, heartbeat)

    print(json.dumps({
        "completed_round": round_no,
        "next_control_round": control.get("round"),
        "mission_stage": mission["current_stage"],
        "mature_symbols": mature,
        "reason": reason,
    }, indent=2))


if __name__ == "__main__":
    main()

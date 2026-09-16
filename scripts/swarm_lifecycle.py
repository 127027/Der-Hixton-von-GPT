"""Known-safe lifecycle repair for the key-free cloud swarm.

This script only normalizes an active mission from NEW to IN_PROGRESS. It never
edits trading code, strategy/risk settings, workflows, credentials or live paths.
The workflow may commit this one metadata repair before specialists run.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.swarm_core import ACTIVE_MISSION_STATES, load_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKBOARD = ROOT / "agent_memory" / "swarm" / "taskboard.json"


class LifecycleError(ValueError):
    """Raised when lifecycle state cannot be repaired safely."""


def normalize_new_mission(
    board: dict[str, Any], *, now: datetime | None = None
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    active = board.get("active_mission")
    if not isinstance(active, dict):
        raise LifecycleError("taskboard.active_mission missing")
    mission_id = str(active.get("id") or "")
    if not mission_id:
        raise LifecycleError("active mission id missing")

    state = str(active.get("state") or "")
    if state == "NEW":
        stamp = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
        active["state"] = "IN_PROGRESS"
        active.setdefault("started_at_utc", stamp)
        active["last_transition_at_utc"] = stamp
        active["last_transition_reason"] = (
            "A10 lifecycle guard auto-repaired known-safe stale NEW state before "
            "specialist execution."
        )
        return board, True, {
            "mission_id": mission_id,
            "before": "NEW",
            "after": "IN_PROGRESS",
            "repair_owner": "A10",
            "repair_class": "MISSION_LIFECYCLE_STALE_NEW",
        }

    if state == "BLOCKED":
        raise LifecycleError("active mission is BLOCKED; automatic repair is not safe")
    if state == "DONE":
        raise LifecycleError("DONE mission cannot remain active")
    if state not in ACTIVE_MISSION_STATES:
        raise LifecycleError(f"invalid active mission state: {state!r}")

    return board, False, {
        "mission_id": mission_id,
        "before": state,
        "after": state,
        "repair_owner": "A10",
        "repair_class": None,
    }


def repair_taskboard(path: Path = DEFAULT_TASKBOARD) -> dict[str, Any]:
    board = load_json(path)
    board, changed, result = normalize_new_mission(board)
    if changed:
        path.write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["changed"] = changed
    result["taskboard"] = str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--taskboard", type=Path, default=DEFAULT_TASKBOARD)
    args = parser.parse_args(argv)
    result = repair_taskboard(args.taskboard)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

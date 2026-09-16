from __future__ import annotations

from datetime import UTC, datetime

import pytest

from scripts.swarm_lifecycle import LifecycleError, normalize_new_mission


def test_new_active_mission_is_safely_normalized() -> None:
    board = {
        "active_mission": {
            "id": "SWARM-X",
            "state": "NEW",
        }
    }
    now = datetime(2026, 9, 16, 12, 34, tzinfo=UTC)
    repaired, changed, evidence = normalize_new_mission(board, now=now)
    mission = repaired["active_mission"]
    assert changed is True
    assert mission["state"] == "IN_PROGRESS"
    assert mission["started_at_utc"] == now.isoformat()
    assert evidence["repair_owner"] == "A10"
    assert evidence["repair_class"] == "MISSION_LIFECYCLE_STALE_NEW"


def test_existing_in_progress_mission_is_not_rewritten() -> None:
    board = {
        "active_mission": {
            "id": "SWARM-X",
            "state": "IN_PROGRESS",
            "started_at_utc": "2026-09-16T12:00:00+00:00",
        }
    }
    repaired, changed, evidence = normalize_new_mission(board)
    assert changed is False
    assert repaired["active_mission"]["state"] == "IN_PROGRESS"
    assert evidence["repair_class"] is None


def test_blocked_mission_is_never_auto_repaired() -> None:
    board = {"active_mission": {"id": "SWARM-X", "state": "BLOCKED"}}
    with pytest.raises(LifecycleError, match="BLOCKED"):
        normalize_new_mission(board)


def test_done_mission_cannot_remain_active() -> None:
    board = {"active_mission": {"id": "SWARM-X", "state": "DONE"}}
    with pytest.raises(LifecycleError, match="DONE"):
        normalize_new_mission(board)

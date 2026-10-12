"""Small durable lifecycle audit, never containing launcher or Binance secrets."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path


def record_session_event(database: Path, instance: str, event: str, reason: str) -> None:
    path = database.parent / "runtime-lifecycle.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 262144:
        path.replace(path.with_suffix(".previous.jsonl"))
    payload = {
        "at_utc": datetime.now(UTC).isoformat(),
        "instance": instance,
        "pid": os.getpid(),
        "event": event,
        "reason": reason,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())

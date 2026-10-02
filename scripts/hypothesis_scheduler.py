"""Select the next evidence-led autonomous research hypothesis."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def select(queue: dict[str, Any], decision: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(decision,dict) and decision.get("action")=="BUILD_ENGINEERING_CANDIDATE_AND_RUN_A01_A11":
        return {
            "schema_version":1,
            "action":"FINISH_VALIDATED_CANDIDATE_BEFORE_NEW_HYPOTHESIS",
            "hypothesis":None,
            "reason":"promotion_path_has_priority",
        }
    hypotheses=queue.get("hypotheses")
    if not isinstance(hypotheses,list):
        raise RuntimeError("hypothesis queue missing")
    ready=[row for row in hypotheses if isinstance(row,dict) and row.get("status")=="READY"]
    if not ready:
        return {
            "schema_version":1,
            "action":"REQUEST_NOVEL_HYPOTHESIS",
            "hypothesis":None,
            "reason":"no_READY_hypothesis",
        }
    row=ready[0]
    return {
        "schema_version":1,
        "action":"RUN_NEXT_BOUNDED_HYPOTHESIS",
        "hypothesis":row,
        "reason":"highest_priority_ready_queue_item",
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser()
    p.add_argument("--queue",type=Path,default=Path("agent_memory/autonomy/hypothesis_queue.json"))
    p.add_argument("--decision",type=Path)
    p.add_argument("--output",type=Path,default=Path("evidence/autonomous-next-hypothesis.json"))
    a=p.parse_args(argv)
    decision=_load(a.decision) if a.decision and a.decision.is_file() else None
    result=select(_load(a.queue),decision)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

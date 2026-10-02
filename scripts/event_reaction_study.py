"""Point-in-time event reaction study for the Hixton research swarm.

Events are not trading commands. This diagnostic measures post-publication market
reaction using only event timestamps already stored in the append-only archive.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.coin_optimization_cycle import _rules

HORIZONS=(1,6,24,72)


def _load(path:Path)->dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _parse(value:str)->datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(UTC)


def _reaction(candles:list[Any], published:datetime)->dict[str,float]|None:
    eligible=[c for c in candles if c.close_time_utc<=published]
    if not eligible:
        return None
    base=eligible[-1].close
    result:dict[str,float]={}
    for hours in HORIZONS:
        target=published+timedelta(hours=hours)
        future=next((c for c in candles if c.close_time_utc>=target),None)
        if future is None:
            continue
        result[f"return_{hours}h_pct"]=(future.close/base-1.0)*100.0
    return result or None


def evaluate(archive:dict[str,Any])->dict[str,Any]:
    events=archive.get("events")
    if not isinstance(events,list) or not events:
        return {
            "schema_version":1,
            "study":"POINT_IN_TIME_EVENT_REACTION",
            "status":"WAITING_FOR_POINT_IN_TIME_EVENTS",
            "event_count":0,
            "rule_candidate":None,
            "activation_performed":False,
        }
    _,start,end=safe_closed_window()
    history=load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=_rules(),
    )
    rows=[]
    for event in events:
        if not isinstance(event,dict):
            continue
        published=_parse(str(event["published_at_utc"]))
        if not (start<=published<=end):
            continue
        symbols=event.get("symbols") or list(V6_COIN_STRATEGY.symbols)
        if symbols==["MARKET"]:
            symbols=list(V6_COIN_STRATEGY.symbols)
        for symbol in symbols:
            candles=history.candles_by_symbol.get(str(symbol),[])
            reaction=_reaction(candles,published)
            if reaction:
                rows.append({
                    "event_id":event.get("id"),
                    "published_at_utc":published.isoformat(),
                    "source_url":event.get("source_url"),
                    "category":event.get("category"),
                    "sentiment":event.get("sentiment"),
                    "symbol":symbol,
                    **reaction,
                })
    summaries={}
    for horizon in HORIZONS:
        key=f"return_{horizon}h_pct"
        values=[float(r[key]) for r in rows if key in r]
        if values:
            summaries[key]={"n":len(values),"mean_pct":mean(values)}
    enough=len(rows)>=50
    return {
        "schema_version":1,
        "study":"POINT_IN_TIME_EVENT_REACTION",
        "status":"EVIDENCE_AVAILABLE" if rows else "NO_EVENTS_IN_WINDOW",
        "event_symbol_observations":len(rows),
        "summary":summaries,
        "minimum_observations_for_rule_candidate":50,
        "rule_candidate":None if not enough else "REQUIRES_WALK_FORWARD_EVENT_RULE_RESEARCH",
        "point_in_time_only":True,
        "research_only":True,
        "activation_performed":False,
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser()
    p.add_argument("--archive",type=Path,default=Path("agent_memory/autonomy/event_archive.json"))
    p.add_argument("--output",type=Path,default=Path("evidence/event-reaction-study.json"))
    a=p.parse_args(argv)
    result=evaluate(_load(a.archive))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

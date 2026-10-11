"""Research-only: temporarily open SUI/UNI's second static backtest gate IN MEMORY.
Canonical sources, V6, Paper, Live and broker accounts are never changed.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path
import hixton.domain.satellite_layer as satellite
from hixton.domain.versions import strategy_definition
from hixton.data.storage import CandleStore
from hixton.data.binance import BinancePublicClient
from hixton.backtest.models import ExecutionRules, CURRENT_COSTS, STRESS_COSTS
from hixton.backtest.continuity import load_continuity_history, continuity_manifest_data
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from research_v8_filler_ablation_20261011 import summary

EXISTING=("NEARUSDC","AAVEUSDC","BCHUSDC")
EXPERIMENTS={
 "baseline":EXISTING,
 "sui_only":("SUIUSDC",),
 "uni_only":("UNIUSDC",),
 "baseline_plus_sui":EXISTING+("SUIUSDC",),
 "baseline_plus_uni":EXISTING+("UNIUSDC",),
 "all_five":EXISTING+("SUIUSDC","UNIUSDC"),
}

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--end",required=True)
 ap.add_argument("--output",default="evidence/research-v8-sui-uni-unlock-20261011.json")
 ap.add_argument("--database",default="data/hixton-usdc.sqlite3")
 args=ap.parse_args()
 end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(UTC)
 start=end.replace(year=end.year-3)
 strategy=strategy_definition("v8")
 if strategy.active_shared_satellites!=EXISTING or satellite.ACTIVE_SHARED_SATELLITES!=EXISTING:
  raise ValueError("Unexpected static gate or V8 baseline")
 db=Path(args.database); rules={}
 with CandleStore(db,read_only=True) as store:
  for symbol in strategy.symbols:
   r=store.load_symbol_rules(symbol)
   if not r or r.status!="TRADING" or not r.spot_allowed or "MARKET" not in r.order_types:
    raise ValueError(f"{symbol}: missing public USDC execution rules")
   rules[symbol]=ExecutionRules(r.tick_size,r.step_size,r.min_qty,r.min_notional)
 history=load_continuity_history(strategy=strategy,report_start_utc=start,report_end_utc=end,
  execution_rules=rules,client=BinancePublicClient(base_url="https://data-api.binance.vision"),
  native_database_path=db,cache_path=db.parent/"backtest-history.sqlite3")
 results={}
 for label,active in EXPERIMENTS.items():
  candidate=replace(strategy,active_shared_satellites=active)
  outputs={};previous=satellite.ACTIVE_SHARED_SATELLITES
  try:
   # This only affects this temporary research Python process, NOT production.
   satellite.ACTIVE_SHARED_SATELLITES=tuple(sorted(set(previous)|set(active)))
   for cost in (CURRENT_COSTS,STRESS_COSTS):
    run=run_shared_portfolio_backtest(
      candles_by_symbol=history.candles_by_symbol,execution_rules=rules,
      starting_cash=D("250"),target_notional=D("125"),slot_count=2,
      strategy=candidate,report_start_utc=start,report_end_utc=end,costs=cost)
    outputs[cost.name]=summary(run,start,end)
    print(label,cost.name,"equity",outputs[cost.name]["ending_equity"],
      "trades",outputs[cost.name]["trades"],flush=True)
  finally:
   satellite.ACTIVE_SHARED_SATELLITES=previous
  results[label]={"active_fillers":list(active),"scenarios":outputs}
 baseline=results["baseline"]["scenarios"]["current"]
 reproducible=(baseline["trades"]==198 and
   abs(D(baseline["ending_equity"])-D("1601.35"))<=D("0.10"))
 restored=satellite.ACTIVE_SHARED_SATELLITES==EXISTING
 for row in results.values():
  row["deltas"]={}
  for cost in ("current","stress"):
   x=row["scenarios"][cost];y=results["baseline"]["scenarios"][cost]
   row["deltas"][cost]={"delta_end_usdc":str(D(x["ending_equity"])-D(y["ending_equity"])),
     "delta_trades":x["trades"]-y["trades"],
     "delta_drawdown_pp":str(D(x["drawdown_pct"])-D(y["drawdown_pct"]))}
 payload={"research_only":True,"no_order_requests":True,
  "strategy_source_unchanged":True,"temporary_in_memory_gate_override":True,
  "canonical_gate_restored":restored,"canonical_baseline_reproduced":reproducible,
  "source_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
  "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  "end_utc":end.isoformat(),"history":continuity_manifest_data(history),
  "experiments":results,"promotion":"NOT_AUTHORIZED_NOT_OOS_VALIDATED"}
 dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n")
 print("SAVED",dest,"canonical",reproducible,"gate_restored",restored,flush=True)
 if not reproducible or not restored: raise RuntimeError("Research integrity gate failed")

if __name__=="__main__":
 main()

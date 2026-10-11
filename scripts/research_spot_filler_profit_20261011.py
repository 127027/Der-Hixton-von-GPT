"""V8 Spot-only 1000/1100-USDC compounding research: profit vs trade cadence.

Historical CMO screens are point-in-time hypotheses, NOT trained or OOS proof.
No changes to canonical V6/V8, Paper, Live, UI or API credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.storage import CandleStore
from hixton.domain.allocation import RANKED_REPEAT
from hixton.domain.models import SignalAction
from hixton.domain.trade_policy import PolicyDecision
from hixton.domain.versions import strategy_definition

from research_capital1100_compound_20261011 import load_patched_module

ORIGINAL_FILLERS = ("NEARUSDC", "AAVEUSDC", "BCHUSDC")
FILLER_CASES = {
    "baseline_3_fillers": ORIGINAL_FILLERS,
    "without_aave_near_bch": ("NEARUSDC", "BCHUSDC"),
    "near_only": ("NEARUSDC",),
    "bch_only": ("BCHUSDC",),
    "aave_only": ("AAVEUSDC",),
    "near_aave": ("NEARUSDC", "AAVEUSDC"),
    "aave_bch": ("AAVEUSDC", "BCHUSDC"),
    "core_only_no_fillers": (),
}
FILTER_CASES = {
    "near_bch_core_cmo025": {
        "fillers": ("NEARUSDC", "BCHUSDC"), "core_min_cmo": 0.25,
        "filler_min_cmo": 0.0,
    },
    "near_bch_core_cmo040": {
        "fillers": ("NEARUSDC", "BCHUSDC"), "core_min_cmo": 0.40,
        "filler_min_cmo": 0.0,
    },
    "near_bch_filler_cmo020": {
        "fillers": ("NEARUSDC", "BCHUSDC"), "core_min_cmo": 0.0,
        "filler_min_cmo": 0.20,
    },
    "near_bch_filler_cmo035": {
        "fillers": ("NEARUSDC", "BCHUSDC"), "core_min_cmo": 0.0,
        "filler_min_cmo": 0.35,
    },
}


def _cadence(fills, start, end):
    times = sorted(f.fill_time_utc for f in fills if f.action is SignalAction.ENTER_LONG)
    intervals = [(b-a).total_seconds()/86400 for a, b in zip(
        [start]+times, times+[end])]
    monthly = Counter(t.strftime("%Y-%m") for t in times)
    no_trade_30d = 0
    left = start
    while left < end:
        right = min(left+timedelta(days=30), end)
        if not any(left <= t < right for t in times):
            no_trade_30d += 1
        left = right
    return {
        "opened_trades": len(times),
        "max_days_between_new_entries_including_edges": round(max(intervals),3),
        "median_days_between_new_entries": round(sorted(intervals)[len(intervals)//2],3),
        "zero_entry_nonoverlapping_30d_periods": no_trade_30d,
        "months_with_new_entries": len(monthly),
        "max_entries_in_calendar_month": max(monthly.values(), default=0),
        "entries_by_calendar_month": dict(sorted(monthly.items())),
        "entries_by_year": {
            str(y):sum(1 for t in times if start.replace(year=start.year+y-1)
                <= t < start.replace(year=start.year+y))
            for y in (1,2,3)
        },
    }


def _summarize(run, start, end, initial, core_names, filler_names):
    m=run.metrics
    prev=initial
    yearly=[]
    for year in (1,2,3):
        boundary=start.replace(year=start.year+year)
        equity=m.ending_equity if boundary==end else next(
            (p.equity for p in reversed(run.equity_curve)
             if p.time_utc < boundary), prev
        )
        yearly.append({"year":year,"end_usdc":str(equity),
                       "pnl_usdc":str(equity-prev)})
        prev=equity
    by_coin=defaultdict(lambda: {"trades":0,"wins":0,"realized_pnl":D(0)})
    for t in run.trades:
        x=by_coin[t.symbol]
        x["trades"]+=1
        x["wins"]+=int(t.realized_pnl>0)
        x["realized_pnl"]+=t.realized_pnl
    by_coin=dict(sorted((sym,{"trades":v["trades"],"wins":v["wins"],
               "realized_pnl":str(v["realized_pnl"])}) for sym,v in by_coin.items()))
    return {
        "ending_equity":str(m.ending_equity),
        "pnl_usdc":str(m.ending_equity-initial),
        "total_completed_trades":m.completed_trades,
        "winning_trades":m.winning_trades,
        "losing_trades":m.losing_trades,
        "max_drawdown_pct":str(m.max_drawdown_pct),
        "fees_usdc":str(m.total_fees),
        "spread_slippage_usdc":str(m.modeled_spread_slippage),
        "exposure_pct":str(m.exposure_pct),
        "profit_factor":str(m.profit_factor),
        "yearly":yearly,
        "per_coin":by_coin,
        "core_trade_count":sum(v["trades"] for s,v in by_coin.items() if s in core_names),
        "active_filler_trade_count":sum(v["trades"] for s,v in by_coin.items() if s in filler_names),
        "cadence":_cadence(run.fills,start,end),
        "blocked_reason_counts":dict(Counter(
            s.rsplit(":",1)[-1] for s in run.blocked_signals)),
        "open_symbols_at_end":list(run.open_symbols_at_end),
    }


def _run(mod, *, strategy, candles, rules, start, end, initial, cost,
         active_fillers, core_min_cmo=0.0, filler_min_cmo=0.0):
    if core_min_cmo<0 or filler_min_cmo<0:
        raise ValueError("invalid screen")
    original_gate=mod.TradePolicyGate
    class CausalResearchGate(original_gate):
        def decide(self, point, **kwargs):
            decision=super().decide(point, **kwargs)
            if decision.block_reason is not None or decision.signal is None:
                return decision
            if decision.signal.action is not SignalAction.ENTER_LONG:
                return decision
            floor=filler_min_cmo if point.symbol in strategy.satellite_symbols else core_min_cmo
            if floor > 0 and (point.abs_cmo or 0.0) < floor:
                return PolicyDecision(decision.signal,block_reason="RESEARCH_LOW_MOMENTUM_CMO")
            return decision
    if core_min_cmo or filler_min_cmo:
        mod.TradePolicyGate=CausalResearchGate
    try:
        profile=replace(strategy,active_shared_satellites=tuple(active_fillers))
        return mod.run_shared_portfolio_backtest(
            candles_by_symbol=candles,
            report_start_utc=start,report_end_utc=end,
            starting_cash=initial, target_notional=initial/D(2),
            slot_count=2,costs=cost,execution_rules=rules,
            strategy=profile,
        )
    finally:
        mod.TradePolicyGate=original_gate


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--database",default="data/hixton-usdc.sqlite3")
    parser.add_argument("--end",required=True)
    parser.add_argument("--output",default="evidence/v8-spot-fillers-compounding-1100.json")
    args=parser.parse_args()
    end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(UTC)
    start=end.replace(year=end.year-3)
    if any((end.minute,end.second,end.microsecond)):
        raise ValueError("Expected full closed UTC hour")
    strategy=strategy_definition("v8")
    if len(strategy.symbols)!=15 or strategy.active_shared_satellites!=ORIGINAL_FILLERS:
        raise ValueError("Unexpected canonical V8: stop")
    db=Path(args.database)
    rules={}
    with CandleStore(db,read_only=True) as store:
        for symbol in strategy.symbols:
            r=store.load_symbol_rules(symbol)
            if not r or r.status!="TRADING" or not r.spot_allowed or "MARKET" not in r.order_types:
                raise ValueError("Missing Spot USDC exchange filters "+symbol)
            rules[symbol]=ExecutionRules(r.tick_size,r.step_size,r.min_qty,r.min_notional)
    history=load_continuity_history(
        strategy=strategy,report_start_utc=start,report_end_utc=end,
        execution_rules=rules,
        client=BinancePublicClient(base_url="https://data-api.binance.vision"),
        native_database_path=db,cache_path=db.parent/"backtest-history.sqlite3",
    )
    mod,canonical_sha,research_sha=load_patched_module()
    cases={}
    configs=[
        (k,D("1100"),fillers,0.0,0.0)
        for k,fillers in FILLER_CASES.items()
    ]+[
        (k,D("1100"),v["fillers"],v["core_min_cmo"],v["filler_min_cmo"])
        for k,v in FILTER_CASES.items()
    ]+[
        ("1000_baseline",D("1000"),ORIGINAL_FILLERS,0.0,0.0),
        ("1000_near_bch",D("1000"),("NEARUSDC","BCHUSDC"),0.0,0.0),
    ]
    for label,initial,fillers,core_floor,filler_floor in configs:
        row={"starting_cash_usdc":str(initial),
             "active_fillers":list(fillers),
             "core_cmo_floor":core_floor,"filler_cmo_floor":filler_floor,
             "scenarios":{}}
        for cost in (CURRENT_COSTS,STRESS_COSTS):
            # The comparative fixed 1000 USDC pair has current/stress too.
            print("CASE",label,cost.name,flush=True)
            output=_run(mod,strategy=strategy,candles=history.candles_by_symbol,
                rules=rules,start=start,end=end,initial=initial,cost=cost,
                active_fillers=fillers,core_min_cmo=core_floor,
                filler_min_cmo=filler_floor)
            row["scenarios"][cost.name]=_summarize(
                output,start,end,initial,
                set(strategy.symbols)-set(strategy.satellite_symbols),
                set(fillers))
            m=row["scenarios"][cost.name]
            print("RESULT",label,cost.name,
                  "end",m["ending_equity"],"trades",m["total_completed_trades"],
                  "gap",m["cadence"]["max_days_between_new_entries_including_edges"],
                  "DD",m["max_drawdown_pct"],flush=True)
        cases[label]=row
    for name,row in cases.items():
        ref=cases["1000_baseline" if name.startswith("1000_") else "baseline_3_fillers"]
        row["vs_same_budget_baseline"]={}
        for cost in ("current","stress"):
            a=row["scenarios"][cost];b=ref["scenarios"][cost]
            row["vs_same_budget_baseline"][cost]={
                "delta_ending_equity_usdc":str(D(a["ending_equity"])-D(b["ending_equity"])),
                "delta_completed_trades":a["total_completed_trades"]-b["total_completed_trades"],
                "delta_max_gap_days":round(
                    a["cadence"]["max_days_between_new_entries_including_edges"] -
                    b["cadence"]["max_days_between_new_entries_including_edges"],3),
                "delta_30day_no_entry_periods":
                    a["cadence"]["zero_entry_nonoverlapping_30d_periods"]-
                    b["cadence"]["zero_entry_nonoverlapping_30d_periods"],
                "delta_last_year_pnl_usdc":
                    str(D(a["yearly"][-1]["pnl_usdc"])-D(b["yearly"][-1]["pnl_usdc"])),
            }
    baseline=cases["baseline_3_fillers"]["scenarios"]["current"]
    expected=D("24672.6274805900223")
    reference_ok=(baseline["total_completed_trades"]==194 and
                  abs(D(baseline["ending_equity"])-expected)<D("0.01"))
    if not reference_ok:
        raise RuntimeError("Canonical 1100 compounding baseline changed; refuse conclusions")
    result={
        "source_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "canonical_source_sha256":canonical_sha,
        "compounding_research_engine_sha256":research_sha,
        "start_utc":start.isoformat(),"end_utc":end.isoformat(),
        "market_universe":list(strategy.symbols),
        "core_coins":list(set(strategy.symbols)-set(strategy.satellite_symbols)),
        "original_active_fillers":list(ORIGINAL_FILLERS),
        "capital_rule":"All trading from shared portfolio: each 2-slot fraction grows/shrinks with current portfolio equity at next execution open, subject to free USDC cash; no borrowed leverage.",
        "historical_price_origin":continuity_manifest_data(history),
        "canonical_1100_compound_baseline_reproduced":reference_ok,
        "no_live_or_paper_orders":True,"no_private_exchange_keys":True,
        "no_product_strategy_edits":True,
        "hypothesis_warning":"CMO thresholds and filler comparisons on already-seen 3Y data; not independent out-of-sample validation; no auto promotion",
        "cases":cases,
        "status":"RESEARCH_ONLY_DO_NOT_PROMOTE",
    }
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("EVIDENCE",target,"cases",len(cases),flush=True)


if __name__=="__main__":
    main()

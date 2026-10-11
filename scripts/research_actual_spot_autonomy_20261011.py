"""Historical 15-market Spot test of the *real* opt-in Paper/Backtest helpers.

No imported private exchange keys, no order endpoints, no leverage.
Known 2023-2026 window was already examined, so results are IN-SAMPLE only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.binance import BinancePublicClient
from hixton.data.storage import CandleStore
from hixton.domain.models import SignalAction
from hixton.domain.versions import strategy_definition

MATRIX=(
    ("baseline_fixed_2",D("1100"),2,False,False),
    ("baseline_compound_2",D("1100"),2,True,False),
    ("quality_compound_2",D("1100"),2,True,True),
    ("quality_compound_3",D("1100"),3,True,True),
    ("quality_compound_4",D("1100"),4,True,True),
    ("quality_compound_1000_2",D("1000"),2,True,True),
    ("quality_compound_1000_4",D("1000"),4,True,True),
)


def summarise(run,initial,start,end):
    m=run.metrics
    times=sorted(f.fill_time_utc for f in run.fills if f.action is SignalAction.ENTER_LONG)
    gaps=[(b-a).total_seconds()/86400 for a,b in zip([start]+times,times+[end])]
    months=Counter(x.strftime("%Y-%m") for x in times)
    yearly=[]; prior=initial
    for y in (1,2,3):
        bound=start.replace(year=start.year+y)
        equity=m.ending_equity if bound==end else next(
            (p.equity for p in reversed(run.equity_curve) if p.time_utc<bound), prior)
        yearly.append({"year":y,"pnl":str(equity-prior),"equity":str(equity)})
        prior=equity
    return {
        "start_usdc":str(initial),"end_usdc":str(m.ending_equity),
        "pnl_usdc":str(m.ending_equity-initial),
        "completed_trades":m.completed_trades,
        "entries":len(times),
        "max_entry_gap_days":round(max(gaps),3),
        "months_with_entry":len(months),
        "max_drawdown_pct":str(m.max_drawdown_pct),
        "fees_usdc":str(m.total_fees),
        "spread_slippage_usdc":str(m.modeled_spread_slippage),
        "exposure_pct":str(m.exposure_pct),
        "yearly":yearly,
        "exit_coins":dict(Counter(t.symbol for t in run.trades)),
        "blocked_reasons":dict(Counter(reason.rsplit(":",1)[-1]
                               for reason in run.blocked_signals)),
    }


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--database",default="data/hixton-usdc.sqlite3")
    a.add_argument("--end",required=True)
    a.add_argument("--output",default="evidence/spot-autonomy-three-year.json")
    args=a.parse_args()
    end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(UTC)
    start=end.replace(year=end.year-3)
    if any((end.minute,end.second,end.microsecond)):
        raise ValueError("requires a closed whole UTC hour")
    strategy=strategy_definition("v8")
    if len(strategy.symbols)!=15:
        raise ValueError("V8 must have 15 observed USDC markets")
    db=Path(args.database); rules={}
    with CandleStore(db,read_only=True) as store:
        for sym in strategy.symbols:
            r=store.load_symbol_rules(sym)
            if r is None or r.status!="TRADING" or not r.spot_allowed or "MARKET" not in r.order_types:
                raise ValueError("Missing exchange market filters "+sym)
            rules[sym]=ExecutionRules(r.tick_size,r.step_size,r.min_qty,r.min_notional)
    history=load_continuity_history(
        strategy=strategy,report_start_utc=start,report_end_utc=end,
        execution_rules=rules,
        client=BinancePublicClient(base_url="https://data-api.binance.vision"),
        native_database_path=db,cache_path=db.parent/"backtest-history.sqlite3")
    results={}
    for name,starting,slots,compound,quality in MATRIX:
        row={"start_usdc":str(starting),"slots":slots,"compounding":compound,
             "quality_filler_screen":quality,"scenarios":{}}
        for costs in (CURRENT_COSTS,STRESS_COSTS):
            print("RUN",name,costs.name,flush=True)
            run=run_shared_portfolio_backtest(
                candles_by_symbol=history.candles_by_symbol,
                report_start_utc=start,report_end_utc=end,
                starting_cash=starting,target_notional=starting/D(slots),
                slot_count=slots,execution_rules=rules,
                strategy=strategy,costs=costs,
                reinvest_profits=compound,autonomous_spot=quality,
            )
            stats=summarise(run,starting,start,end)
            row["scenarios"][costs.name]=stats
            print("RESULT",name,costs.name,stats["end_usdc"],
                  stats["completed_trades"],stats["max_entry_gap_days"],flush=True)
        results[name]=row
    for name,row in results.items():
        benchmark=results["baseline_compound_2"]["scenarios"]
        row["vs_baseline_compound"]={}
        for cost,stats in row["scenarios"].items():
            row["vs_baseline_compound"][cost]={
                "delta_usdc":str(D(stats["end_usdc"])-D(benchmark[cost]["end_usdc"])),
                "delta_trades":stats["completed_trades"]-benchmark[cost]["completed_trades"],
            }
    result={
        "source_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "market_count":len(strategy.symbols),
        "period_start":start.isoformat(),
        "period_end":end.isoformat(),
        "starting_budget_definition":"one shared USDC wallet, never one full budget per coin",
        "test_kind":"IN_SAMPLE_HISTORICAL_COMPARISON_NOT_FUTURE_FORECAST",
        "strategy":strategy.version,
        "no_leverage":True,
        "no_private_credentials":True,
        "no_live_orders":True,
        "data":continuity_manifest_data(history),
        "results":results,
    }
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("DONE",out,flush=True)


if __name__=="__main__":
    main()

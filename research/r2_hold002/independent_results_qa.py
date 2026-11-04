"""Independent post-economic auditor for all 16 original-context R2-D1-HOLD-002 outcomes.

Read-only: recompute from original emitted hourly equity, fills, and trades.
This is NOT an engine rerun, not a future/holdout experiment or product approval.
"""
import csv,gzip,hashlib,json,pathlib
from collections import defaultdict
from datetime import datetime,timedelta
from decimal import Decimal as D

HIST=("original_32k","current_26oct","latest_long")
SYN=("cycles","winter","whipsaw","rotation","tail")
KEYS=[w+"__"+cost for w in HIST+SYN for cost in ("current","stress")]

def d(x):
    v=D(str(x))
    if not v.is_finite():raise RuntimeError("NONFINITE_MONEY")
    return v
def dt(x):return datetime.fromisoformat(str(x).replace("Z","+00:00"))
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
    return h.hexdigest()
def epis(rows,start):
    peak=start;peak_dt=rows[0]["t"];amax=pmax=None
    for i,p in enumerate(rows):
        if p["equity"]>peak:peak=p["equity"];peak_dt=p["t"]
        v=peak-p["equity"]
        if v<=0:continue
        f=v/peak*100
        event={"peak_utc":peak_dt,"trough_utc":p["t"],"peak_equity_usdc":peak,
               "trough_equity_usdc":p["equity"],"loss_usdc":v,"loss_pct":f,"idx":i}
        if amax is None or v>amax["loss_usdc"]:amax=event
        if pmax is None or f>pmax["loss_pct"]:pmax=event
    def closure(x):
        if not x:return None
        r=next((p["t"] for p in rows[x["idx"]+1:] if p["equity"]>=x["peak_equity_usdc"]),None)
        return {**{k:str(v) if isinstance(v,D) else v.isoformat() if isinstance(v,datetime) else v for k,v in x.items() if k!="idx"},
                "recovered_at_utc":r.isoformat() if r is not None else None,
                "recovery_hours_after_trough":str(d((r-x["trough_utc"]).total_seconds()/3600)) if r else None,
                "not_recovered_within_window":r is None}
    return closure(amax),closure(pmax)
def assert_episode(actual,calculated):
    if (actual is None)!=(calculated is None):raise RuntimeError("DRAW_DOWN_EPISODE_NULL_MISMATCH")
    if actual is None:return
    for k,v in calculated.items():
        if actual[k]!=v:
            if k.endswith("_utc"):
                if dt(actual[k])!=dt(v):raise RuntimeError("HWM_TIME_MISMATCH:"+k)
            elif k.endswith(("_usdc","_pct","_trough")) or k=="recovery_hours_after_trough":
                if d(actual[k])!=d(v):raise RuntimeError("HWM_VALUE_MISMATCH:"+k)
            else:
                raise RuntimeError("HWM_EPISODE_MISMATCH:"+k)
def run(root):
    report={"scope":"16 candidate original-context independent ledger audits; no re-run, no independent mark-price verification",
            "source_candidate":"R2-D1-HOLD-002","cases":{},"errors":[],
            "candidate_promotion":False,"passed":0,"total_hours":0,"status":"STARTED"}
    try:
        cases={}
        for key in KEYS:
            p=root/key
            row=json.loads((p/"Result.json").read_text())
            complete=json.loads((p/"Complete.json").read_text())
            for filename,expected in complete["files_sha256"].items():
                if sha(p/filename)!=expected:raise RuntimeError("SHA256_MISMATCH_"+key+"_"+filename)
            if row["candidate"]!="R2-D1-HOLD-002" or row["frozen_product"]!="f56d48536525830dd6ea50bf5bc174a6f9aeff8c":
                raise RuntimeError("WRONG_CANDIDATE_OR_SOURCE_"+key)
            with gzip.open(p/"Equity.csv.gz","rt",encoding="utf-8-sig") as f:
                reader=csv.DictReader(f)
                if set(reader.fieldnames)!={"time_utc","equity","cash","position_value"}:
                    raise RuntimeError("UNEXPECTED_EQUITY_COLUMNS_"+key)
                ticks=[];last=None
                for x in reader:
                    t=dt(x["time_utc"]);eq=d(x["equity"]);cash=d(x["cash"]);position=d(x["position_value"])
                    if last and t-last!=timedelta(hours=1):raise RuntimeError("NONCONTIGUOUS_HOURS_"+key)
                    last=t
                    if eq<0 or cash<0 or position<0:raise RuntimeError("NEGATIVE_ACCOUNT_BALANCE_"+key)
                    if eq!=cash+position:raise RuntimeError("CASH_PLUS_MARKED_VALUE_NOT_EQUITY_"+key)
                    ticks.append({"t":t,"equity":eq,"cash":cash,"marked":position})
            if not ticks:raise RuntimeError("EMPTY_HOURLY_LEDGER_"+key)
            signals=json.loads((p/"Signals.json").read_text())
            fills=json.loads((p/"Fills.json").read_text())
            trades=json.loads((p/"Trades.json").read_text())
            ids={s["signal_id"]:s for s in signals}
            if len(ids)!=len(signals):raise RuntimeError("DUPLICATE_SIGNAL_"+key)
            initial=d(row["native_metrics"]["starting_equity"])
            # Every fill must correspond to an existing causal signal and a native next-open.
            by_open=defaultdict(list)
            qty=defaultdict(D)
            for f in fills:
                s=ids[f["signal_id"]]
                tm=dt(f["fill_time_utc"]);signal=dt(s["candle_close_time_utc"])
                if tm!=signal+timedelta(milliseconds=1):raise RuntimeError("LOOKAHEAD_FILL_"+key)
                if d(f["base_quantity"])<=0 or d(f["fee_quote_equivalent"])<0:
                    raise RuntimeError("BAD_FILL_QTY_OR_FEE_"+key)
                by_open[tm].append((f,s))
            cash=initial
            cash_max_gap=D(0)
            fill_events=0
            for tick in ticks:
                open_time=tick["t"]-timedelta(hours=1)+timedelta(milliseconds=1)
                for f,s in by_open.get(open_time,()):
                    symbol=s["symbol"]
                    amount=d(f["base_quantity"])
                    if f["action"]=="ENTER_LONG":
                        cash-=d(f["quote_value"]);qty[symbol]+=amount
                    elif f["action"]=="EXIT_LONG":
                        cash+=d(f["quote_value"])-d(f["fee_quote_equivalent"])
                        qty[symbol]-=amount
                    else:raise RuntimeError("INVALID_FILL_SIDE_"+key)
                    if qty[symbol]<-D("0.000000001"):raise RuntimeError("NEGATIVE_NATIVE_COIN_OWNERSHIP_"+key)
                    fill_events+=1
                gap=abs(cash-tick["cash"]);cash_max_gap=max(cash_max_gap,gap)
                if cash!=tick["cash"]:raise RuntimeError("FILL_TO_CASH_LEDGER_MISMATCH_"+key)
            if fill_events!=len(fills):raise RuntimeError("UNACCOUNTED_FILL_"+key)
            if ticks[-1]["equity"]!=d(row["candidate_ending_equity_usdc"]):raise RuntimeError("WRONG_END_EQUITY_"+key)
            if sum((d(f["fee_quote_equivalent"]) for f in fills),D(0))!=d(row["native_total_fill_fees_usdc"]):
                raise RuntimeError("FILL_FEES_SUM_MISMATCH_"+key)
            if sum((d(f["modeled_spread_slippage"]) for f in fills),D(0))!=d(row["native_modeled_adverse_spread_slippage_usdc"]):
                raise RuntimeError("FILL_SLIPPAGE_SUM_MISMATCH_"+key)
            for trade in trades:
                if d(trade["exit_quote_receive"])-d(trade["entry_quote_spend"])!=d(trade["realized_pnl"]):
                    raise RuntimeError("TRADE_REALIZED_PNL_MISMATCH_"+key)
            absdd,pctdd=epis(ticks,initial)
            assert_episode(row["maximum_absolute_drawdown_episode"],absdd)
            assert_episode(row["maximum_percentage_drawdown_episode"],pctdd)
            if d(row["candidate_max_drawdown_pct"])!=d(pctdd["loss_pct"] if pctdd else 0):
                raise RuntimeError("MAX_DD_PERCENT_METRIC_MISMATCH_"+key)
            quarters=[]
            if key.split("__")[0] in SYN:
                quarters=json.loads((p/"Quarters.json").read_text())
                if len(quarters)!=20:raise RuntimeError("NOT_20_QUARTERS_"+key)
                qsum=sum(int(q["hours"]) for q in quarters)
                if qsum!=len(ticks):raise RuntimeError("QUARTER_HOURS_NOT_ALL_INCLUDED_"+key)
                if d(quarters[-1]["end_equity_usdc"])!=ticks[-1]["equity"]:
                    raise RuntimeError("QUARTER_END_EQUITY_NOT_LEDGER_"+key)
                first=initial
                for q in quarters:
                    if d(q["start_equity_usdc"])!=first:
                        raise RuntimeError("QUARTER_RESET_"+key)
                    if d(q["net_pnl_usdc"])!=d(q["end_equity_usdc"])-first:
                        raise RuntimeError("QUARTER_BAD_DELTA_"+key)
                    first=d(q["end_equity_usdc"])
            events=row["events"]
            triggers=[e for e in events if e["kind"]=="TRIGGER"]
            episodes_seen=[e["episode"] for e in triggers]
            if len(episodes_seen)!=len(set(episodes_seen)):
                raise RuntimeError("DUPLICATE_EPISODE_"+key)
            for e in events:
                if e["kind"]=="TRIM_EXECUTED":
                    st=dt(e["signal_close_utc"]);ot=dt(e["fill_open_utc"])
                    if ot!=st+timedelta(milliseconds=1):
                        raise RuntimeError("BAD_R2_SPECIAL_EXIT_NEXT_OPEN_"+key)
            cases[key]={"ending_equity":row["candidate_ending_equity_usdc"],
              "baseline_ending_equity":row["baseline_ending_equity_usdc"],
              "dd_pct":row["candidate_max_drawdown_pct"],"fills":len(fills),"trades":len(trades),
              "hours":len(ticks),"quarter_count":len(quarters),"cash_drift_usdc":str(cash_max_gap),
              "fees_usdc":row["native_total_fill_fees_usdc"],"slippage_usdc":row["native_modeled_adverse_spread_slippage_usdc"],
              "r2_trigger_episodes":len(triggers)}
            report["cases"][key]=cases[key];report["passed"]+=1;report["total_hours"]+=len(ticks)
            print("INDEPENDENT_R2_FINANCIAL_QA_CASE",key,"PASS",json.dumps(cases[key]),flush=True)
        if report["passed"]!=16:raise RuntimeError("NOT_16_CASES")
        report["status"]="R2_SECOND_16_NATIVE_LEDGER_QA_PASS_WITH_LIMITED_MARK_TO_MARKET_SCOPE"
    except Exception as exc:
        report["status"]="FAILED";report["errors"].append(str(exc))
    return report
if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--out",required=True);args=ap.parse_args()
    res=run(pathlib.Path(args.input))
    pathlib.Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(res,indent=2)+"\n")
    print("INDEPENDENT_R2_FINANCIAL_QA_STATUS",json.dumps({k:res[k] for k in ("status","passed","total_hours","errors")}),flush=True)
    if res["status"]!="R2_SECOND_16_NATIVE_LEDGER_QA_PASS_WITH_LIMITED_MARK_TO_MARKET_SCOPE":raise SystemExit(1)

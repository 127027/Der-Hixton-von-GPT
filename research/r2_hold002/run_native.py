"""Isolated native f56 R2-D1-HOLD-002 researcher. NEVER imports live trading.

Uses the same f56 Input-Contract.json and original loader formats. The f56
portfolio module itself is never modified on disk. R2 hook is compiled in a
new, explicitly research-only module, and original source SHA is asserted.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,calendar,io,os,pathlib,runpy,sys,types
from dataclasses import asdict,is_dataclass
from datetime import UTC,datetime,timedelta
from decimal import Decimal as D, ROUND_DOWN
from enum import Enum

def offline(event,args):
    if event.startswith("socket."):
        raise RuntimeError("R2_RESEARCH_NETWORK_FORBIDDEN")
sys.addaudithook(offline)
sys.dont_write_bytecode=True

FROZEN="f56d48536525830dd6ea50bf5bc174a6f9aeff8c"
FROZEN_SOURCE="5cf39658dc6b1ee827ec0daefd73b2384a9edd0ff116ba0203f9ab8bb7737797"
FROZEN_NATIVE_PORTFOLIO_SHA="06da08bf4e63613a5c655eaa34a3361d0b192645e1d128cf545e4075c0401dfd"
OWN="R2-D1-HOLD-002"
HIST=("original_32k","current_26oct","latest_long")
SYNTH=("cycles","winter","whipsaw","rotation","tail")
COSTS=("current","stress")

def digest(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open("rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""):
            h.update(b)
    return h.hexdigest()
def primitive(v):
    if is_dataclass(v):return primitive(asdict(v))
    if isinstance(v,datetime):return v.isoformat()
    if isinstance(v,(D,pathlib.Path)):return str(v)
    if isinstance(v,Enum):return v.value
    if isinstance(v,dict):return {str(k):primitive(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [primitive(x) for x in v]
    return v
def write(path,obj):
    path=pathlib.Path(path)
    if path.exists():raise RuntimeError("NO_OUTPUT_OVERWRITE:"+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(primitive(obj),indent=2,ensure_ascii=False)+"\n")

def snapshot_loader(*,bundle,kind,window):
    """Exact source loader transformations, independently matched by snapshot hash."""
    sys.path.insert(0,str(bundle/"engine/src"))
    root=bundle/"engine/src"
    datamod=types.ModuleType("hixton.data")
    datamod.__path__=[str(root/"hixton/data")]
    datamod.__package__="hixton.data"
    sys.modules["hixton.data"]=datamod
    from hixton.backtest.engine import candle_snapshot_sha256
    from hixton.backtest.models import CostModel,ExecutionRules
    from hixton.domain.market_rules import FILTER_DECIMALS
    from hixton.domain.models import Candle
    from hixton.domain.versions import strategy_definition
    contract=json.loads((bundle/"Input-Contract.json").read_text())
    if contract["source_commit"]!=FROZEN or contract["source_sha256_normalized"]!=FROZEN_SOURCE:
        raise RuntimeError("ORIGINAL_INPUT_CONTRACT_FROZEN_SOURCE_MISMATCH")
    base=strategy_definition("v8r")
    if base.config_payload()!=contract["strategy"]:
        raise RuntimeError("ORIGINAL_ACTIVE_PROFILE_CONTRACT_MISMATCH")
    spec=contract["windows"][window]
    paths=spec["data_files"]
    def sourcepath(v):
        p=(bundle/v["path"]).resolve(strict=True)
        if not p.is_relative_to(bundle.resolve()):raise RuntimeError("INPUT_PATH_ESCAPE")
        if digest(p)!=v["sha256"]:raise RuntimeError("INDIVIDUAL_INPUT_SHA_MISMATCH")
        return p
    if kind=="historical":
        if "joint" in paths:
            raw=json.loads(gzip.decompress(sourcepath(paths["joint"]).read_bytes()))
        else:
            raw={sym:json.loads(gzip.decompress(sourcepath(v).read_bytes())) for sym,v in paths.items()}
        data={s:[Candle(**{**r,"open_time_utc":datetime.fromisoformat(r["open_time_utc"]),
                                     "close_time_utc":datetime.fromisoformat(r["close_time_utc"])})
                  for r in raw[s]] for s in base.symbols}
    else:
        import numpy as np
        manifest=json.loads(sourcepath(paths["manifest"]).read_text())
        if manifest["synthetic_not_forecast"] is not True:raise RuntimeError("SYNTHETIC_WORLD_DECLARATION_MISSING")
        if tuple(manifest["symbols"])!=base.symbols:raise RuntimeError("ORIGINAL_SYMBOL_ORDER_MISMATCH")
        data={s:[] for s in manifest["symbols"]}
        with np.load(sourcepath(paths["npz"]),allow_pickle=False) as a:
            if a.files!=["values"]:raise RuntimeError("BAD_ORIGINAL_NPZ_KEYS")
            values=a["values"]
            if list(values.shape)!=spec["array_shape"] or values.dtype.kind!="f" or values.dtype.itemsize!=8:
                raise RuntimeError("BAD_ORIGINAL_ARRAY_SHAPE_OR_DTYPE")
            if not np.isfinite(values).all():raise RuntimeError("NONFINITE_OHLC")
            start=datetime.fromisoformat(spec["start"])
            for i,row in enumerate(values):
                at=start+timedelta(hours=i-spec["warmup_bars"])
                for j,s in enumerate(manifest["symbols"]):
                    op,hi,lo,cl,vol,quote,count=row[j]
                    data[s].append(Candle(s,at,at+timedelta(hours=1,milliseconds=-1),
                        float(op),float(hi),float(lo),float(cl),float(vol),float(quote),
                        int(count),True,spec["candle_source_used_for_snapshot"]))
    observed={s:candle_snapshot_sha256(v) for s,v in data.items()}
    if observed!=spec["snapshots"]:raise RuntimeError("NATIVE_LOADER_SNAPSHOT_PARITY_FAIL")
    rules={s:ExecutionRules(**{k:D(v) if k in FILTER_DECIMALS else v for k,v in r.items()})
           for s,r in spec["rules"].items()}
    return data,spec,contract,base,rules,CostModel

def episodes(result):
    curve=result.equity_curve
    hwm=result.starting_cash
    t0=curve[0].time_utc
    hwm_time=t0
    best_abs=best_pct=None
    for i,row in enumerate(curve):
        if row.equity>hwm:hwm=row.equity;hwm_time=row.time_utc
        dd=hwm-row.equity
        pct=dd/hwm*100 if hwm>0 else D(0)
        if dd>0:
            v={"peak_utc":hwm_time,"trough_utc":row.time_utc,
               "peak_equity_usdc":hwm,"trough_equity_usdc":row.equity,
               "loss_usdc":dd,"loss_pct":pct,"idx":i}
            if best_abs is None or dd>best_abs["loss_usdc"]:best_abs=v
            if best_pct is None or pct>best_pct["loss_pct"]:best_pct=v
    def restore(v):
        if v is None:return None
        i=v["idx"];p=v["peak_equity_usdc"]
        next_recovery=next((x.time_utc for x in curve[i+1:] if x.equity>=p),None)
        return {**{k:w for k,w in v.items() if k!="idx"},
                "recovered_at_utc":next_recovery,
                "recovery_hours_after_trough":D(str((next_recovery-v["trough_utc"]).total_seconds()/3600)) if next_recovery else None,
                "not_recovered_within_window":next_recovery is None}
    return restore(best_abs),restore(best_pct)
def addmonths(anchor,n):
    y=anchor.year+(anchor.month-1+n)//12
    m=(anchor.month-1+n)%12+1
    return anchor.replace(year=y,month=m,day=min(anchor.day,calendar.monthrange(y,m)[1]))
def quarters(result,spec):
    a=datetime.fromisoformat(spec["start"])
    e=datetime.fromisoformat(spec["end"])
    if e!=a.replace(year=a.year+5):return None
    b=[addmonths(a,3*i) for i in range(21)]
    assert len(b)==21 and b[-1]==e
    grouped=[[] for _ in range(20)]
    for point in result.equity_curve:
        t=point.time_utc
        i=next((k for k in range(20) if b[k]<=t<b[k+1]),None)
        if i is None:raise RuntimeError("QUARTER_UNASSIGNED")
        grouped[i].append(point)
    if any(not a for a in grouped):raise RuntimeError("EMPTY_3MO_QUARTER")
    start=result.starting_cash
    out=[]
    for i,g in enumerate(grouped):
        p=g[-1];end=p.equity
        out.append({"quarter":i+1,"start_utc":b[i],"end_exclusive_utc":b[i+1],
                    "start_equity_usdc":start,"end_equity_usdc":end,
                    "net_pnl_usdc":end-start,
                    "net_return_pct":(end-start)/start*100 if start else None,
                    "closing_cash_usdc":p.cash,"closing_position_usdc":p.position_value,
                    "hours":len(g)})
        start=end
    if start!=result.equity_curve[-1].equity:raise RuntimeError("QUARTER_RESET_OR_END_MISMATCH")
    return out

def load_baseline(bundle,spec,cost):
    p=bundle/spec["baseline"][cost]["path"]
    return json.loads((p/"Result.json").read_text()),p

def assert_native(result,reference,*,window,cost,bundle,spath,control=False):
    if result.metrics.starting_equity!=result.starting_cash or result.metrics.ending_equity!=result.equity_curve[-1].equity:
        raise RuntimeError("BAD_RESULT_METRIC_EQUITY")
    if any(p.equity!=p.cash+p.position_value for p in result.equity_curve):
        raise RuntimeError("NATIVE_CASH_MARKED_EQUITY_NOT_CONSERVED")
    if any(b.time_utc-a.time_utc!=timedelta(hours=1) for a,b in zip(result.equity_curve,result.equity_curve[1:])):
        raise RuntimeError("NATIVE_NONCONTINUOUS_HOURS")
    ids={s.signal_id:s for s in result.signals}
    if len(ids)!=len(result.signals):raise RuntimeError("DUPLICATE_SIGNAL_ID")
    for f in result.fills:
        if f.signal_id not in ids:raise RuntimeError("UNLINKED_FILL_SIGNAL_ID")
        if f.fill_time_utc!=ids[f.signal_id].candle_close_time_utc+timedelta(milliseconds=1):
            raise RuntimeError("FUTURE_LEAK_FILL_TIME")
    if control:
        def normalized(x):
            return primitive(x)
        if normalized(result.metrics)!=reference["metrics"]:
            raise RuntimeError("INSTRUMENTED_DISABLED_C0_METRICS_MISMATCH")
        for n,val in (("Fills.json",result.fills),("Trades.json",result.trades),("Signals.json",result.signals)):
            original=json.loads((spath/n).read_text())
            if normalized(val)!=original:raise RuntimeError("INSTRUMENTED_DISABLED_C0_"+n+"_MISMATCH")
        with gzip.open(spath/"Equity.csv.gz","rt",encoding="utf-8") as f:
            lines=csv.reader(f)
            head=next(lines)
            if head!=["time_utc","equity","cash","position_value"]:raise RuntimeError("Unexpected original ledger headers")
            for old,new in zip(lines,result.equity_curve,strict=True):
                if [datetime.fromisoformat(old[0]).isoformat(),*old[1:]]!=[
                    new.time_utc.isoformat(),str(new.equity),str(new.cash),str(new.position_value)]:
                    raise RuntimeError("INSTRUMENTED_DISABLED_C0_HOURLY_MONEY_MISMATCH")

def run(args):
    bundle=pathlib.Path(args.bundle).resolve(strict=True)
    output=pathlib.Path(args.out).resolve()
    if output.exists() or output.is_relative_to(bundle):raise RuntimeError("OUT_PATH_EXISTS_OR_OVERLAPS_ORIGINAL")
    if args.window in HIST and args.kind!="historical" or args.window in SYNTH and args.kind!="synthetic":
        raise RuntimeError("WINDOW_KIND_MISMATCH")
    import runpy
    original_runner=bundle/("run_baseline.py" if args.kind=="historical" else "run_synthetic_baseline.py")
    source_run=runpy.run_path(str(original_runner),run_name="r2_frozen_original_verify")
    contract,manifest=source_run["verify"]()
    data,spec,loaded_contract,base,rules,CostModel=snapshot_loader(bundle=bundle,kind=args.kind,window=args.window)
    if loaded_contract!=contract:raise RuntimeError("CONTRACT_CHANGES_INSIDE_RUN")
    from research.r2_hold002.held_policy import HeldRiskKernel,instrument
    orig=(bundle/"engine/src/hixton/backtest/portfolio.py").read_text(encoding="utf-8")
    if hashlib.sha256(orig.encode()).hexdigest()!=FROZEN_NATIVE_PORTFOLIO_SHA:
        raise RuntimeError("FROZEN_F56_NATIVE_SOURCE_MISMATCH")
    src=instrument(orig)
    policy=HeldRiskKernel(enabled=args.mode=="candidate")
    mod=types.ModuleType("hixton.backtest.r2_hold001_isolated")
    mod.__file__=str(pathlib.Path(__file__).resolve())
    mod.__package__="hixton.backtest"
    mod.R2_POLICY=policy
    sys.modules[mod.__name__]=mod
    exec(compile(src,mod.__file__,"exec"),mod.__dict__)
    model=CostModel(**{k:D(v) if k!="name" else v for k,v in contract["costs"][args.cost].items()})
    seed=D(spec["seed"])
    result=mod.run_shared_portfolio_backtest(candles_by_symbol=data,
        report_start_utc=datetime.fromisoformat(spec["start"]),
        report_end_utc=datetime.fromisoformat(spec["end"]),starting_cash=seed,
        target_notional=(seed/2).quantize(D(".01"),rounding=ROUND_DOWN),
        slot_count=2,costs=model,execution_rules=rules,strategy=base,
        reinvest_profits=True,profit_reinvestment_fraction=D(1),
        capital_exposure_fraction=D(1),autonomous_spot=True)
    baseline,basepath=load_baseline(bundle,spec,args.cost)
    assert_native(result,baseline,window=args.window,cost=args.cost,bundle=bundle,spath=basepath,control=args.mode=="control")
    output.mkdir(parents=True)
    absdd,pctdd=episodes(result)
    q=quarters(result,spec)
    fees=sum((x.fee_quote_equivalent for x in result.fills),D(0))
    adverse=sum((x.modeled_spread_slippage for x in result.fills),D(0))
    baseline_metrics=baseline["metrics"]
    baseline_end=D(baseline_metrics["ending_equity"])
    # This is aggregate opportunity cost only, not a coin-attributable counterfactual.
    end_delta=result.metrics.ending_equity-baseline_end
    row={"window":args.window,"cost":args.cost,"mode":args.mode,
         "candidate":OWN if args.mode=="candidate" else "CONTROL_PATCHED_DISABLED",
         "frozen_product":FROZEN,"source_sha256":FROZEN_SOURCE,
         "native_portfolio_sha256":FROZEN_NATIVE_PORTFOLIO_SHA,
         "research_overlay_sha256":hashlib.sha256(src.encode()).hexdigest(),
         "input_contract_sha256":digest(bundle/"Input-Contract.json"),
         "original_archive_verified_by_native_manifest":True,
         "data_snapshot_sha256_by_symbol":result.data_snapshot_sha256_by_symbol,
         "baseline_ending_equity_usdc":baseline_end,
         "candidate_ending_equity_usdc":result.metrics.ending_equity,
         "ending_equity_delta_vs_C0_usdc":end_delta,
         "aggregate_net_ending_equity_opportunity_cost_vs_C0_usdc":max(D(0),-end_delta),
         "candidate_max_drawdown_pct":result.metrics.max_drawdown_pct,
         "native_metrics":result.metrics,
         "maximum_absolute_drawdown_episode":absdd,
         "maximum_percentage_drawdown_episode":pctdd,
         "native_total_fill_fees_usdc":fees,
         "native_modeled_adverse_spread_slippage_usdc":adverse,
         "fills":len(result.fills),"trades":len(result.trades),
         "event_counts":{k:sum(v["kind"]==k for v in policy.events)
                         for k in ("TRIGGER","TRIM_EXECUTED","TRIM_SKIPPED_MARKET_FILTER",
                                   "TRIM_SKIPPED_NATIVE_EXIT","REARM")},
         "events":policy.events,"quarter_count":len(q) if q else None,
         "worst_quarter_net_usdc":min((x["net_pnl_usdc"] for x in q),default=None) if q else None,
         "worst_quarter_return_pct":min((x["net_return_pct"] for x in q),default=None) if q else None,
         "no_live_order_or_product_change":True}
    write(output/"Result.json",row)
    write(output/"Fills.json",result.fills)
    write(output/"Trades.json",result.trades)
    write(output/"Signals.json",result.signals)
    if q:write(output/"Quarters.json",q)
    with gzip.open(output/"Equity.csv.gz","wt",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(("time_utc","equity","cash","position_value"))
        w.writerows((p.time_utc,p.equity,p.cash,p.position_value) for p in result.equity_curve)
    write(output/"Complete.json",{"complete":True,"files_sha256":{p.name:digest(p) for p in output.iterdir() if p.is_file()},
          "source_commit":FROZEN,"case":args.window+"__"+args.cost,
          "candidate":OWN if args.mode=="candidate" else "CONTROL_PATCHED_DISABLED",
          "candidate_total_ends":result.metrics.ending_equity})
    print("R2_NATIVE_CASE",json.dumps({"window":args.window,"cost":args.cost,
       "mode":args.mode,"status":"NATIVE_FINANCIAL_LEDGER_RECORDED",
       "candidate_end":str(result.metrics.ending_equity),"C0_end":str(baseline_end),
       "dd_pct":str(result.metrics.max_drawdown_pct),
       "trims":row["event_counts"].get("TRIM_EXECUTED"),"quarters":len(q) if q else None}),flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--bundle",required=True)
    ap.add_argument("--kind",choices=("historical","synthetic"),required=True)
    ap.add_argument("--window",required=True)
    ap.add_argument("--cost",choices=COSTS,required=True)
    ap.add_argument("--mode",choices=("control","candidate"),required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    run(a)
if __name__=="__main__":main()

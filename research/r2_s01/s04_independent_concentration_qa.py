"""Independent S04 read-only QA against frozen native hourly series and original close prices."""
from __future__ import annotations
import argparse,json,gzip,pathlib,collections
from decimal import Decimal as D
from datetime import datetime,timedelta
from research.r2_hold003.run_native import snapshot_loader

def load(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:return json.load(f)

def verify(raw,summary,dd,closes,seed):
    rows=raw["rows"];assert len(rows)==26304
    high=seed;ht=None;absloss=D(-1);pctloss=D(-1);abs_event=pct_event=None
    counts=collections.Counter();sum_e=D(0);sum_i=D(0);active=0;last=None
    for row in rows:
        stamp=row["utc"]
        now=datetime.fromisoformat(stamp)
        if last is not None and now-last!=timedelta(hours=1):raise RuntimeError("S04_QA_GAP")
        last=now
        eq=D(row["equity"]);cash=D(row["cash"]);val=D(0);invest=D(0);largest=D(0)
        for sym,prices in closes.items():
            price=prices[stamp]
            q=D(row["positions"].get(sym,{}).get("qty","0"))
            dust=D(row["dust"].get(sym,"0"))
            iv=q*price
            invest+=iv;val+=(q+dust)*price
            largest=max(largest,iv)
        if val!=D(row["position_value"]) or cash+val!=eq:
            raise RuntimeError("S04_QA_RECONCILIATION_MISMATCH")
        if row["positions"]:
            active+=1;counts["regular_position_hours"]+=1
            sum_e+=largest/eq;sum_i+=largest/invest
        elif any(D(v)>0 for v in row["dust"].values()):
            counts["dust_only_no_regular_hours"]+=1
        else:counts["cash_only_hours"]+=1
        if eq>high:high=eq;ht=stamp
        dl=high-eq;dp=dl/high*D(100)
        if dl>absloss:
            absloss=dl;abs_event=(ht or rows[0]["utc"],stamp,high,eq,dl,dp)
        if dp>pctloss:
            pctloss=dp;pct_event=(ht or rows[0]["utc"],stamp,high,eq,dl,dp)
    assert sum(counts.values())==26304
    for key,val in counts.items():assert summary[key]==val,(key,summary[key],val)
    assert D(summary["mean_largest_regular_coin_over_total_equity_pct_ACTIVE_ONLY"])==sum_e/D(active)*D(100)
    assert D(summary["mean_largest_regular_coin_over_regular_invested_pct_ACTIVE_ONLY"])==sum_i/D(active)*D(100)
    for name,ev in (("max_absolute",abs_event),("max_percentage",pct_event)):
        origin=dd[name]
        fields=["peak_utc","trough_utc","peak_equity","trough_equity","drawdown_usdc","drawdown_pct"]
        if any(str(v)!=str(origin[k]) for k,v in zip(fields,ev)):
            raise RuntimeError("S04_QA_DRAWDOWN_EPISODE_MISMATCH:"+name)
    return {"regular_position_hours":active,"cash_only_hours":counts["cash_only_hours"],
        "dust_only_no_regular_hours":counts["dust_only_no_regular_hours"],
        "average_biggest_coin_pct_of_equity_when_held":str(sum_e/D(active)*D(100)),
        "average_biggest_coin_pct_of_invested_when_held":str(sum_i/D(active)*D(100)),
        "max_absolute_dd":dd["max_absolute"],"max_percent_dd":dd["max_percentage"]}

def main(args):
    bundle=pathlib.Path(args.bundle).resolve(strict=True)
    data,spec,contract,*_=snapshot_loader(bundle=bundle,kind="historical",window="original_32k")
    assert contract["source_commit"]=="f56d48536525830dd6ea50bf5bc174a6f9aeff8c"
    closes={sym:{c.close_time_utc.isoformat():D(str(c.close)) for c in bars} for sym,bars in data.items()}
    report=json.loads(pathlib.Path(args.report).read_text())
    a=load(args.control);b=load(args.candidate)
    assert len(report["confirmed_s01_exit_24h_matched_cash_and_concentration"])==52
    c=verify(a,report["C0_summary"],report["C0_drawdown_episodes"],closes,D(spec["seed"]))
    s=verify(b,report["S01_summary"],report["S01_drawdown_episodes"],closes,D(spec["seed"]))
    for w in report["matched_utc_episode_windows"].values():
        lo=w["owner_episode"]["peak_utc"];hi=w["owner_episode"]["trough_utc"]
        for label,rows in (("C0",a["rows"]),("S01",b["rows"])):
            selected=[r for r in rows if lo<=r["utc"]<=hi]
            assert len(selected)==w[label+"_at_identical_utc"]["hours"]
            assert selected[0]["utc"]==lo and selected[-1]["utc"]==hi
            assert str(D(selected[-1]["equity"])-D(selected[0]["equity"]))==w[label+"_at_identical_utc"]["period_equity_change_usdc"]
    output={"id":"R2-S04-CONCENTRATION-001","status":"S04_INDEPENDENT_RAW_CONCENTRATION_HWM_QA_PASS",
        "C0":c,"S01":s,"matched_utc_episode_windows":list(report["matched_utc_episode_windows"]),
        "verified_52_sale_windows":52,"verified_hourly_marked_equity":26304,
        "limited_descriptive_not_causal_or_tradable":True,"product_unchanged":True}
    path=pathlib.Path(args.output)
    if path.exists():raise RuntimeError("S04_QA_NO_OVERWRITE")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,indent=2)+"\n")
    print("S04_INDEPENDENT_QA_RESULT",json.dumps(output),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ("bundle","report","control","candidate","output"):p.add_argument("--"+field,required=True)
    main(p.parse_args())

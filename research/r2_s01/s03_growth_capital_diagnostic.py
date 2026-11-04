"""S03-CAP-001: frozen-C0 vs rejected-S01 capital utilization, no trading replay."""
from __future__ import annotations
import argparse,collections,gzip,json,pathlib
from decimal import Decimal as D
from datetime import datetime,timedelta
from research.r2_hold003.run_native import snapshot_loader
def read(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:return json.load(f)
def d(x):return D(str(x))
def compute(rows,close,seed):
    n=len(rows)
    cash_fraction_sum=D(0);invested_fraction_sum=D(0)
    max_coin_fraction_sum=D(0);slot_hours=0
    cash_gt_half=cash_gt_quarter=zero_regular=0
    concentration_gt_half=0
    months={}; exposure_by_coin=collections.defaultdict(lambda:D(0))
    position_count_hours=collections.Counter()
    max_concentration=(D(0),None,None)
    for row in rows:
        t=row["utc"]
        ec=d(row["equity"]);ca=d(row["cash"]);pv=d(row["position_value"])
        assert ec>0 and ca+pv==ec
        cf=ca/ec
        cash_fraction_sum+=cf;invested_fraction_sum+=pv/ec
        cash_gt_half+=int(cf>D(".5"));cash_gt_quarter+=int(cf>D(".25"))
        zero_regular+=int(not row["positions"])
        slot_hours+=row["occupied_slots"]
        position_count_hours[len(row["positions"])]+=1
        marked=D(0)
        largest=D(0);largest_coin=None
        for sym in close:
            quote=close[sym].get(t)
            if quote is None:raise RuntimeError("S03_CANDLE_TIME_MISSING:"+sym+":"+t)
            q=d(row["positions"].get(sym,{}).get("qty","0"))
            dust=d(row["dust"].get(sym,"0"))
            v=(q+dust)*quote
            marked+=v
            if q>0:
                regular=q*quote
                exposure_by_coin[sym]+=regular
                if regular>largest:largest=regular;largest_coin=sym
        if marked!=pv:
            raise RuntimeError("S03_ORIGINAL_F56_MARKED_EQUITY_MISMATCH:"+t+":"+str(marked-pv))
        concentration=largest/ec
        max_coin_fraction_sum+=concentration
        concentration_gt_half+=int(concentration>D(".5"))
        if concentration>max_concentration[0]:max_concentration=(concentration,t,largest_coin)
        month=t[:7]
        if month not in months:
            months[month]=dict(first_utc=t,last_utc=t,hours=0,last_equity=ec,
                               cash_fraction_sum=D(0),invested_fraction_sum=D(0))
        m=months[month];m["last_utc"]=t;m["hours"]+=1;m["last_equity"]=ec
        m["cash_fraction_sum"]+=cf;m["invested_fraction_sum"]+=pv/ec
    prior=seed;monthly=[]
    for month,m in sorted(months.items()):
        nextend=m["last_equity"]
        monthly.append(dict(month=month,first_utc=m["first_utc"],last_utc=m["last_utc"],hours=m["hours"],
                            opening_equity_usdc=str(prior),closing_equity_usdc=str(nextend),
                            change_usdc=str(nextend-prior),
                            change_pct=str((nextend/prior-D(1))*D(100)),
                            average_cash_pct=str(m["cash_fraction_sum"]/D(m["hours"])*D(100)),
                            average_invested_pct=str(m["invested_fraction_sum"]/D(m["hours"])*D(100))))
        prior=nextend
    assert sum(x["hours"] for x in monthly)==n
    assert prior==d(rows[-1]["equity"])
    return dict(rows=n,starting_equity_usdc=str(seed),ending_equity_usdc=str(prior),
                time_average_cash_pct=str(cash_fraction_sum/D(n)*D(100)),
                time_average_invested_pct=str(invested_fraction_sum/D(n)*D(100)),
                hours_cash_gt_25pct=cash_gt_quarter,
                hours_cash_gt_50pct=cash_gt_half,
                hours_zero_regular_held=zero_regular,
                occupied_native_slot_hours=slot_hours,
                time_average_largest_regular_coin_pct_of_equity=str(max_coin_fraction_sum/D(n)*D(100)),
                hours_largest_regular_coin_gt_50pct_equity=concentration_gt_half,
                max_coin_concentration=dict(pct=str(max_concentration[0]*D(100)),
                                            utc=max_concentration[1],coin=max_concentration[2]),
                total_regular_held_usdc_hours_by_coin={k:str(v) for k,v in sorted(exposure_by_coin.items())},
                active_position_count_hour_distribution=dict(sorted(position_count_hours.items())),
                month_count=len(monthly),monthly=monthly)
def run(a):
    bundle=pathlib.Path(a.bundle).resolve(strict=True)
    data,spec,contract,base,rules,CostModel=snapshot_loader(bundle=bundle,kind="historical",window="original_32k")
    if contract["source_commit"]!="f56d48536525830dd6ea50bf5bc174a6f9aeff8c":
        raise RuntimeError("S03_FROZEN_SOURCE_MISMATCH")
    closes={sym:{c.close_time_utc.isoformat():D(str(c.close)) for c in series}
            for sym,series in data.items()}
    c0=read(a.control);s01=read(a.candidate)
    assert len(c0["rows"])==len(s01["rows"])==26304
    assert c0["rows"][0]["utc"]==s01["rows"][0]["utc"]
    seed=D(spec["seed"])
    ref_c=compute(c0["rows"],closes,seed)
    ref_s=compute(s01["rows"],closes,seed)
    assert D(ref_c["ending_equity_usdc"])==D("33867.79699289748400000000")
    assert D(ref_s["ending_equity_usdc"])==D("10967.68139761524970000000")
    paired=[]
    for x,y in zip(ref_c["monthly"],ref_s["monthly"],strict=True):
        assert x["month"]==y["month"] and x["hours"]==y["hours"]
        paired.append(dict(month=x["month"],end_C0=x["closing_equity_usdc"],
            end_S01=y["closing_equity_usdc"],end_diff_S01_minus_C0=str(d(y["closing_equity_usdc"])-d(x["closing_equity_usdc"])),
            C0_average_cash_pct=x["average_cash_pct"],S01_average_cash_pct=y["average_cash_pct"],
            C0_month_growth_pct=x["change_pct"],S01_month_growth_pct=y["change_pct"]))
    report=dict(id="R2-S03-CAP-001",status="EXACT_NATIVE_CLOSED_MARK_PRICES_CAPITAL_DIAGNOSTIC",
      research_only=True,original_frozen="f56d48536525830dd6ea50bf5bc174a6f9aeff8c",
      original_window="original_32k/current",source_observation_run=41889629161,
      total_hours=26304,zero_hourly_coin_mark_residuals=True,month_reset=False,
      C0=ref_c,S01=ref_s,paired_monthly=paired,
      time_average_cash_pct_delta_S01_minus_C0=
        str(d(ref_s["time_average_cash_pct"])-d(ref_c["time_average_cash_pct"])),
      time_average_invested_pct_delta_S01_minus_C0=
        str(d(ref_s["time_average_invested_pct"])-d(ref_c["time_average_invested_pct"])),
      native_slot_hours_delta_S01_minus_C0=
        ref_s["occupied_native_slot_hours"]-ref_c["occupied_native_slot_hours"],
      observation_not_causal_portfolio_parameter_recommendation=True,
      no_new_market_allocation_strategy_run=True,
      no_product_or_live_change=True)
    path=pathlib.Path(a.output)
    if path.exists():raise RuntimeError("S03_NO_RESULT_OVERWRITE")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n")
    print("R2_S03_CAPITAL_GROWTH_RESULT",json.dumps({
      "total_hours":report["total_hours"],"months":len(paired),
      "C0_average_cash_pct":ref_c["time_average_cash_pct"],
      "S01_average_cash_pct":ref_s["time_average_cash_pct"],
      "C0_average_invested_pct":ref_c["time_average_invested_pct"],
      "S01_average_invested_pct":ref_s["time_average_invested_pct"],
      "C0_slot_hours":ref_c["occupied_native_slot_hours"],
      "S01_slot_hours":ref_s["occupied_native_slot_hours"],
      "C0_concentration_average_pct":ref_c["time_average_largest_regular_coin_pct_of_equity"],
      "S01_concentration_average_pct":ref_s["time_average_largest_regular_coin_pct_of_equity"],
      "C0_cash_gt_50pct_hours":ref_c["hours_cash_gt_50pct"],
      "S01_cash_gt_50pct_hours":ref_s["hours_cash_gt_50pct"]},flush=True))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for n in ("control","candidate","bundle","output"):p.add_argument("--"+n,required=True)
    run(p.parse_args())

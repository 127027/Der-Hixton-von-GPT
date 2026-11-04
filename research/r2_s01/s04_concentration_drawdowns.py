"""S04 observational concentration/drawdown audit, frozen f56 native hourly state."""
from __future__ import annotations
import argparse,gzip,json,pathlib,collections
from decimal import Decimal as D
from datetime import datetime,timedelta
from research.r2_hold003.run_native import snapshot_loader

def load(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:return json.load(f)

def compute(raw,closes):
    rows=raw["rows"];out=[];counts=collections.Counter()
    for r in rows:
        E=D(r["equity"]);cash=D(r["cash"]);native_v=D(r["position_value"])
        I=D(0);dust=D(0);coin_values={}
        for sym,prices in closes.items():
            mark=prices.get(r["utc"])
            if mark is None:raise RuntimeError("S04_MISSING_EXACT_CLOSED_PRICE:"+sym+":"+r["utc"])
            pos=r["positions"].get(sym)
            qty=D(pos["qty"]) if pos is not None else D(0)
            dqty=D(r["dust"].get(sym,"0"))
            iv=qty*mark
            if qty>0:coin_values[sym]=iv
            I+=iv;dust+=dqty*mark
        if I+dust!=native_v or cash+native_v!=E:
            raise RuntimeError("S04_NATIVE_CASH_COINS_DUST_RECONCILIATION_FAILED:"+r["utc"])
        if E<=0:raise RuntimeError("S04_NONPOSITIVE_EQUITY")
        active=bool(coin_values)
        typ="active" if active else ("dust_only" if dust>0 else "cash_only")
        counts[typ]+=1
        large_sym=max(coin_values,key=lambda x:(coin_values[x],x)) if active else None
        largest=coin_values.get(large_sym,D(0)) if active else D(0)
        out.append(dict(utc=r["utc"],E=E,cash=cash,I=I,dust=dust,
            largest=largest,symbol=large_sym,denom_total=largest/E if active else None,
            denom_invested=largest/I if active else None,
            cash_ratio=cash/E,investment_ratio=I/E,position_type=typ,
            positions=len(coin_values),slots=r["occupied_slots"]))
    if len(out)!=26304 or sum(counts.values())!=26304:raise RuntimeError("S04_26304_HOUR_REQUIREMENT")
    return out,counts

def episodes(stats,seed):
    high=seed;high_utc=None
    absolute=None;percentage=None
    for r in stats:
        if r["E"]>high:
            high=r["E"];high_utc=r["utc"]
        loss=high-r["E"]
        pct=loss/high*D(100)
        item=dict(peak_utc=high_utc or stats[0]["utc"],peak_equity=str(high),
                  trough_utc=r["utc"],trough_equity=str(r["E"]),
                  drawdown_usdc=str(loss),drawdown_pct=str(pct))
        if absolute is None or loss>D(absolute["drawdown_usdc"]):absolute=item
        if percentage is None or pct>D(percentage["drawdown_pct"]):percentage=item
    return dict(max_absolute=absolute,max_percentage=percentage)

def period(rows,lo,hi):
    sample=[r for r in rows if lo<=r["utc"]<=hi]
    if not sample:raise RuntimeError("S04_EMPTY_EPISODE")
    active=[r for r in sample if r["position_type"]=="active"]
    cash_only=sum(r["position_type"]=="cash_only" for r in sample)
    dust_only=sum(r["position_type"]=="dust_only" for r in sample)
    s=lambda items,key:sum((r[key] for r in items),D(0))
    top_equity=max(active,key=lambda r:r["denom_total"]) if active else None
    top_invest=max(active,key=lambda r:r["denom_invested"]) if active else None
    return dict(start_utc=lo,end_utc=hi,hours=len(sample),
        start_equity=str(sample[0]["E"]),end_equity=str(sample[-1]["E"]),
        period_equity_change_usdc=str(sample[-1]["E"]-sample[0]["E"]),
        active_regular_hours=len(active),cash_only_hours=cash_only,dust_only_no_regular_hours=dust_only,
        mean_cash_pct_all_hours=str(s(sample,"cash_ratio")/D(len(sample))*D(100)),
        mean_regular_investment_pct_all_hours=str(s(sample,"investment_ratio")/D(len(sample))*D(100)),
        mean_largest_regular_coin_over_total_equity_pct_ACTIVE_ONLY=
            str(s(active,"denom_total")/D(len(active))*D(100)) if active else None,
        mean_largest_regular_coin_over_regular_invested_pct_ACTIVE_ONLY=
            str(s(active,"denom_invested")/D(len(active))*D(100)) if active else None,
        max_largest_coin_over_total_equity=dict(utc=top_equity["utc"],coin=top_equity["symbol"],pct=str(top_equity["denom_total"]*D(100))) if active else None,
        max_largest_coin_over_regular_invested=dict(utc=top_invest["utc"],coin=top_invest["symbol"],pct=str(top_invest["denom_invested"]*D(100))) if active else None,
        start_cash=str(sample[0]["cash"]),end_cash=str(sample[-1]["cash"]),
        start_regular_invested=str(sample[0]["I"]),end_regular_invested=str(sample[-1]["I"]),
        end_largest_coin=sample[-1]["symbol"],
        end_largest_coin_held_value=str(sample[-1]["largest"]))

def global_summary(rows,counts):
    active=[r for r in rows if r["position_type"]=="active"]
    s=lambda samples,k:sum((r[k] for r in samples),D(0))
    return dict(hours=len(rows),cash_only_hours=counts["cash_only"],
        dust_only_no_regular_hours=counts["dust_only"],regular_position_hours=counts["active"],
        cash_only_plus_dust_only_plus_active_equal_all_hours=True,
        mean_cash_pct_all_hours=str(s(rows,"cash_ratio")/D(len(rows))*D(100)),
        mean_regular_investment_pct_all_hours=str(s(rows,"investment_ratio")/D(len(rows))*D(100)),
        mean_largest_regular_coin_over_total_equity_pct_ACTIVE_ONLY=str(s(active,"denom_total")/D(len(active))*D(100)) if active else None,
        mean_largest_regular_coin_over_regular_invested_pct_ACTIVE_ONLY=str(s(active,"denom_invested")/D(len(active))*D(100)) if active else None,
        mean_largest_regular_coin_over_total_equity_pct_ALL_HOURS_WITH_ZERO_FOR_NO_POSITION=str(s(active,"denom_total")/D(len(rows))*D(100)),
        mean_occupied_slots=str(s(rows,"slots")/D(len(rows))))

def run(args):
    from research.r2_hold003.run_native import snapshot_loader
    bundle=pathlib.Path(args.bundle).resolve(strict=True)
    data,spec,contract,base,rules,costs=snapshot_loader(bundle=bundle,kind="historical",window="original_32k")
    if contract["source_commit"]!="f56d48536525830dd6ea50bf5bc174a6f9aeff8c":raise RuntimeError("S04_F56_DRIFT")
    closes={sym:{c.close_time_utc.isoformat():D(str(c.close)) for c in items} for sym,items in data.items()}
    ctrl=load(args.control);candidate=load(args.candidate)
    C,cn=compute(ctrl,closes);S,sn=compute(candidate,closes)
    if any(c["utc"]!=s["utc"] for c,s in zip(C,S,strict=True)):raise RuntimeError("S04_C0_S01_UNALIGNED")
    if C[-1]["E"]!=D("33867.79699289748400000000") or S[-1]["E"]!=D("10967.68139761524970000000"):
        raise RuntimeError("S04_ORIGINAL_NATIVE_END_DRIFT")
    ce=episodes(C,D(spec["seed"]));se=episodes(S,D(spec["seed"]))
    windows={}
    for owner,ep in (("C0",ce),("S01",se)):
        for label,e in ep.items():
            tag=owner+"_"+label
            windows[tag]=dict(owner=owner,kind=label,
                owner_episode=e,C0_at_identical_utc=period(C,e["peak_utc"],e["trough_utc"]),
                S01_at_identical_utc=period(S,e["peak_utc"],e["trough_utc"]))
    previous=json.loads(pathlib.Path(args.previous_s01).read_text())
    events=[e for e in previous["s01_events"] if e["kind"]=="FILLED_NATIVE_FULL_EXIT"]
    assert len(events)==52
    byutc={r["utc"]:i for i,r in enumerate(C)}
    samples=[]
    for e in events:
        t=datetime.fromisoformat(e["fill_utc"])
        close=(t+timedelta(hours=1)-timedelta(milliseconds=1)).isoformat()
        if close not in byutc:raise RuntimeError("S04_MISSING_S01_SALE_CLOSED_HOUR")
        i=byutc[close];hi=min(i+24,len(C)-1)
        samples.append(dict(symbol=e["symbol"],utc=e["fill_utc"],closed_utc=close,
            next_24h_C0=period(C,C[i]["utc"],C[hi]["utc"]),
            next_24h_S01=period(S,S[i]["utc"],S[hi]["utc"])))
    out=dict(id="R2-S04-CONCENTRATION-001",
        status="NATIVE_MATCHED_DRAWDOWN_AND_TWO_DENOMINATOR_CONCENTRATION",
        scope="ORIGINAL_32K_CURRENT_DEVELOPMENT_ONLY",row_count=len(C),
        frozen_product=contract["source_commit"],original_contract_source=contract["source_sha256_normalized"],
        C0_summary=global_summary(C,cn),S01_summary=global_summary(S,sn),
        C0_drawdown_episodes=ce,S01_drawdown_episodes=se,
        matched_utc_episode_windows=windows,
        confirmed_s01_exit_24h_matched_cash_and_concentration=samples,
        sale_event_count=len(samples),
        denominators="Largest REGULAR coin closed mark / full equity; separately / marked REGULAR invested assets",
        undefined_invested_concentration_when_no_active=True,
        causal_protected_wealth_not_estimated=True,
        observation_is_not_strategy_approval=True,not_independent_out_of_sample=True)
    path=pathlib.Path(args.output)
    if path.exists():raise RuntimeError("S04_NO_OVERWRITE")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("S04_TWO_DENOM_DRAWDOWN_RESULT",json.dumps({
        "C0_categories":{k:v for k,v in out["C0_summary"].items() if k.endswith("_hours")},
        "S01_categories":{k:v for k,v in out["S01_summary"].items() if k.endswith("_hours")},
        "C0_concentration_total_ACTIVE_pct":out["C0_summary"]["mean_largest_regular_coin_over_total_equity_pct_ACTIVE_ONLY"],
        "S01_concentration_total_ACTIVE_pct":out["S01_summary"]["mean_largest_regular_coin_over_total_equity_pct_ACTIVE_ONLY"],
        "C0_concentration_invested_ACTIVE_pct":out["C0_summary"]["mean_largest_regular_coin_over_regular_invested_pct_ACTIVE_ONLY"],
        "S01_concentration_invested_ACTIVE_pct":out["S01_summary"]["mean_largest_regular_coin_over_regular_invested_pct_ACTIVE_ONLY"],
        "drawdowns":{k:v for k,v in windows.items() if k.startswith("C0_")}},default=str)[:11000],flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for n in ("bundle","control","candidate","previous-s01","output"):p.add_argument("--"+n,required=True)
    run(p.parse_args())

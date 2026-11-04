"""S03 separate raw-hourly auditing implementation, not a trading/rebalancing policy."""
from __future__ import annotations
import argparse,gzip,json,pathlib,collections
from datetime import datetime,timedelta
from decimal import Decimal as D
from research.r2_hold003.run_native import snapshot_loader
def load(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:return json.load(f)
def inspect(raw,summary,close):
    rows=raw["rows"]
    seed=D("1092.05773944")
    cashsum=D(0);concsum=D(0);cash_over_half=0;slot_hours=0
    month_last={};month_count=collections.Counter()
    prior_t=None
    for row in rows:
        t=datetime.fromisoformat(row["utc"])
        if prior_t and t-prior_t!=timedelta(hours=1):
            raise RuntimeError("S03_QA_TIME_GAP")
        prior_t=t
        equity=D(row["equity"]);cash=D(row["cash"]);pos=D(row["position_value"])
        assert cash+pos==equity
        cashsum+=cash/equity;cash_over_half+=int(cash/equity>D(".5"))
        slot_hours+=row["occupied_slots"]
        marked=D(0);largest=D(0)
        for symbol,prices in close.items():
            price=prices.get(row["utc"])
            if price is None:raise RuntimeError("S03_QA_CLOSE_TIME_MISSING:"+symbol)
            p=row["positions"].get(symbol)
            qty=D(p["qty"]) if p else D(0)
            dust=D(row["dust"].get(symbol,"0"))
            regular=price*qty
            marked+=(qty+dust)*price
            if regular>largest:largest=regular
        if marked!=pos:raise RuntimeError("S03_QA_NATIVE_CLOSED_PRICE_MARK_MISMATCH")
        concsum+=largest/equity
        key=row["utc"][:7];month_last[key]=equity;month_count[key]+=1
    n=D(len(rows))
    assert len(rows)==26304
    assert cashsum/n*D(100)==D(summary["time_average_cash_pct"])
    assert concsum/n*D(100)==D(summary["time_average_largest_regular_coin_pct_of_equity"])
    assert cash_over_half==summary["hours_cash_gt_50pct"]
    assert slot_hours==summary["occupied_native_slot_hours"]
    assert len(month_last)==len(summary["monthly"])==37
    previous=seed
    for m in summary["monthly"]:
        key=m["month"]
        assert m["hours"]==month_count[key]
        assert D(m["opening_equity_usdc"])==previous
        assert D(m["closing_equity_usdc"])==month_last[key]
        assert D(m["change_usdc"])==month_last[key]-previous
        previous=month_last[key]
    assert D(summary["ending_equity_usdc"])==previous
    return dict(hours=len(rows),monthly=len(month_last),concentration_sum_pct=str(concsum/n*D(100)),
                cash_pct=str(cashsum/n*D(100)),slot_hours=slot_hours)
def run(a):
    from research.r2_hold003.run_native import snapshot_loader
    data,spec,contract,base,rules,CostModel=snapshot_loader(bundle=pathlib.Path(a.bundle).resolve(strict=True),kind="historical",window="original_32k")
    assert contract["source_commit"]=="f56d48536525830dd6ea50bf5bc174a6f9aeff8c"
    closes={sym:{c.close_time_utc.isoformat():D(str(c.close)) for c in bars}
            for sym,bars in data.items()}
    c=load(a.control);s=load(a.candidate)
    rep=json.loads(pathlib.Path(a.report).read_text())
    x=inspect(c,rep["C0"],closes)
    y=inspect(s,rep["S01"],closes)
    assert D(rep["C0"]["ending_equity_usdc"])==D("33867.79699289748400000000")
    assert D(rep["S01"]["ending_equity_usdc"])==D("10967.68139761524970000000")
    assert rep["observation_not_causal_portfolio_parameter_recommendation"]
    out=dict(id="R2-S03-CAP-001-SEPARATE-QA",status="S03_NATIVE_CAPITAL_GROWTH_DIAGNOSTIC_QA_PASS",
        source_run=41891428521, original_hourly_run=41889629161,
        C0=x,S01=y, original_closed_mark_price_per_coin_exact=True,
        no_monthly_capital_reset=True,
        no_new_portfolio_rule_proven=True,
        causal_inference_not_claimed=True,
        no_product_or_live_change=True)
    path=pathlib.Path(a.output)
    if path.exists():raise RuntimeError("S03_QA_RESULT_EXISTS")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,indent=2)+"\n")
    print("S03_INDEPENDENT_NATIVE_CAPITAL_QA_PASS",json.dumps(out),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for n in ("control","candidate","report","bundle","output"):p.add_argument("--"+n,required=True)
    run(p.parse_args())

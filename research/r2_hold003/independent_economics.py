"""Read-only post-economic comparison of preregistered HOLD-003 to sealed HOLD-002
and independently reconciled original C0. No native replay, no product promotion.
"""
from __future__ import annotations
import argparse,json,pathlib
from decimal import Decimal as D

HIST=("original_32k","current_26oct","latest_long")
SYN=("cycles","winter","whipsaw","rotation","tail")
COST=("current","stress")
CASES=tuple(w+"__"+c for w in HIST+SYN for c in COST)

def dec(x):
    z=D(str(x))
    if not z.is_finite():
        raise ValueError("Non-finite monetary result")
    return z

def evaluate(candidate_dir,previous_dir,prior_report):
    prior=json.loads(pathlib.Path(prior_report).read_text())
    if prior.get("status")!="HOLD002_16_NATIVE_LEDGER_QA_AND_C0_ECONOMIC_COMPARISON_PASS":
        raise ValueError("Previous independent HOLD002 C0 economic review not PASS")
    if set(prior["cases"])!=set(CASES):
        raise ValueError("Missing prior 16 context C0 DD references")
    result={"candidate":"R2-D1-HOLD-003","previous":"R2-D1-HOLD-002",
       "frozen_product":"f56d48536525830dd6ea50bf5bc174a6f9aeff8c",
       "promotion_allowed":False,"candidate_results_economic_only":True,
       "cases":{},"status":"STARTED"}
    plusC0=[];minusC0=[];equalC0=[];plus002=[];minus002=[];equal002=[]
    worseDD=[];betterDD=[]
    hist_current=[]
    for key in CASES:
        c3=json.loads((pathlib.Path(candidate_dir)/key/"Result.json").read_text())
        c2=json.loads((pathlib.Path(previous_dir)/key/"Result.json").read_text())
        if c3["candidate"]!="R2-D1-HOLD-003" or c2["candidate"]!="R2-D1-HOLD-002":
            raise ValueError("Candidate labels incorrect: "+key)
        if c3["frozen_product"]!=result["frozen_product"] or c2["frozen_product"]!=result["frozen_product"]:
            raise ValueError("Product version changed: "+key)
        for k in ("source_sha256","native_portfolio_sha256","input_contract_sha256","data_snapshot_sha256_by_symbol"):
            if c3[k]!=c2[k]:
                raise ValueError("Different original inputs/native engine: "+key+" "+k)
        baseline=dec(c3["baseline_ending_equity_usdc"])
        previous=dec(c2["candidate_ending_equity_usdc"])
        current=dec(c3["candidate_ending_equity_usdc"])
        if dec(c2["baseline_ending_equity_usdc"])!=baseline or dec(prior["cases"][key]["C0_end_usdc"])!=baseline:
            raise ValueError("C0 end mismatch: "+key)
        delta0=current-baseline;delta2=current-previous
        dd3=dec(c3["candidate_max_drawdown_pct"]);dd2=dec(c2["candidate_max_drawdown_pct"])
        origdd=prior["cases"][key].get("C0_max_dd_pct")
        if origdd is not None:
            origdd=dec(origdd)
            if dd3>origdd:worseDD.append(key)
            elif dd3<origdd:betterDD.append(key)
        if delta0>0:plusC0.append(key)
        elif delta0<0:minusC0.append(key)
        else:equalC0.append(key)
        if delta2>0:plus002.append(key)
        elif delta2<0:minus002.append(key)
        else:equal002.append(key)
        if key in [w+"__current" for w in HIST]:hist_current.append(key)
        events=c3["event_counts"]
        result["cases"][key]={
            "C0_end_usdc":str(baseline),"HOLD002_end_usdc":str(previous),
            "HOLD003_end_usdc":str(current),"delta_003_vs_C0_usdc":str(delta0),
            "delta_003_vs_002_usdc":str(delta2),
            "C0_max_drawdown_pct":str(origdd) if origdd is not None else None,
            "HOLD002_max_drawdown_pct":str(dd2),
            "HOLD003_max_drawdown_pct":str(dd3),
            "003_minus_C0_maxdd_pp":str(dd3-origdd) if origdd is not None else None,
            "003_minus_002_maxdd_pp":str(dd3-dd2),
            "003_largest_absolute_HWM_loss":c3["maximum_absolute_drawdown_episode"],
            "003_largest_percentage_HWM_loss":c3["maximum_percentage_drawdown_episode"],
            "003_worst_quarter_net_usdc":c3["worst_quarter_net_usdc"],
            "003_native_total_fees_usdc":c3["native_total_fill_fees_usdc"],
            "002_native_total_fees_usdc":c2["native_total_fill_fees_usdc"],
            "003_native_modeled_adverse_slippage_usdc":c3["native_modeled_adverse_spread_slippage_usdc"],
            "003_candidate_trim_count":events.get("TRIM_EXECUTED",0),
            "003_no_underwater_trim_skips":events.get("TRIM_SKIPPED_NOT_UNDERWATER",0),
            "003_trigger_count":events.get("TRIGGER",0),
            "003_quarter_count":c3["quarter_count"]
        }
    result["summary"]={
        "003_vs_C0_better_cases":plusC0,"003_vs_C0_worse_cases":minusC0,"003_vs_C0_equal_cases":equalC0,
        "003_vs_002_better_cases":plus002,"003_vs_002_worse_cases":minus002,"003_vs_002_equal_cases":equal002,
        "five_year_003_drawdown_worse_than_C0":worseDD,
        "five_year_003_drawdown_better_than_C0":betterDD,
        "three_historical_current_deltas_usdc":{key:result["cases"][key]["delta_003_vs_C0_usdc"] for key in hist_current},
        "hist_current_end_non_degradation":all(dec(result["cases"][key]["delta_003_vs_C0_usdc"])>=0 for key in hist_current),
        "stress_end_non_degradation":all(dec(result["cases"][k]["delta_003_vs_C0_usdc"])>=0 for k in CASES if k.endswith("__stress")),
        "synthetic_maxDD_non_worsening":not worseDD,
        "tradeoff_note":"Economic-only, no new code/policy QA in this report. Original success floors and independent true holdout not relaxed or proven. No automatic production promotion."
    }
    result["status"]="HOLD003_FULL_16_CONTEXT_COMPARISON_REVIEWED_NO_PROMOTION"
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True)
    p.add_argument("--previous",required=True)
    p.add_argument("--prior-economic-report",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    try:
        x=evaluate(args.candidate,args.previous,args.prior_economic_report)
    except Exception as exc:
        x={"status":"FAILED","candidate":"R2-D1-HOLD-003","errors":[str(exc)],"promotion_allowed":False}
    pathlib.Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(args.output).write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n")
    print("HOLD003_ECONOMIC_REVIEW",json.dumps({"status":x["status"],"summary":x.get("summary"),"errors":x.get("errors")}),flush=True)
    if x["status"]!="HOLD003_FULL_16_CONTEXT_COMPARISON_REVIEWED_NO_PROMOTION":raise SystemExit(1)

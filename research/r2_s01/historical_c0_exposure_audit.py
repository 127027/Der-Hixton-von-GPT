"""Read-only event-time exposure audit on frozen native historical C0 ledgers.

This is diagnostic-only; neither an exit strategy simulation nor proof of
regular, active or sellable held positions, as native fills can leave non-tradable
dust behind. It uses only historical fills and closed hourly equity values.
Historical original windows overlap and must not be counted as independent OOS.
"""
import csv,gzip,json,pathlib,sys,hashlib
from datetime import datetime,timedelta
from decimal import Decimal as D

FROZEN="f56d48536525830dd6ea50bf5bc174a6f9aeff8c"
START=D("1092.05773944")
WINDOWS=("original_32k","current_26oct","latest_long")
COSTS=("current","stress")
CUTS=(D("0.10"),D("0.15"),D("0.30"))

def decimal(s):
    x=D(str(s))
    if not x.is_finite():raise ValueError("NON_FINITE")
    return x
def instant(s):
    x=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if x.utcoffset()!=timedelta(0):raise ValueError("NON_UTC_TIME")
    return x

def holdings_snapshot(t,curve,qty,peak,drawdown):
    held={s:str(q) for s,q in sorted(qty.items()) if q>0}
    return {"closed_bar_utc":t.isoformat(),
            "hwm_equity_usdc":str(peak),"equity_usdc":str(curve["equity"]),
            "cash_usdc":str(curve["cash"]),
            "marked_position_value_usdc":str(curve["position_value"]),
            "portfolio_drawdown_pct":str(drawdown*D(100)),
            "nonzero_balance_symbols_including_possible_dust":list(held),
            "nonzero_coin_quantities_including_possible_dust":held,
            "native_regular_held_positions":"NOT_RECONSTRUCTED",
            "native_occupied_slots":"NOT_RECONSTRUCTED",
            "tradable_minimums_at_event_time":"NOT_PROVEN",
            "actual_native_order_reservations":"NOT_PROVEN",
            "held_cost_basis_at_close":"NOT_PROVEN",
            "EMA72_from_original_candles":"NOT_YET_COMPUTED",
            "ATR24_from_original_candles":"NOT_YET_COMPUTED",
            "did_next_open_native_exit_execute":"NOT_CHECKED"}

def inspect_case(bundle,window,cost,contract):
    spec=contract["windows"][window]
    base=(bundle/spec["baseline"][cost]["path"]).resolve()
    if not base.is_relative_to(bundle.resolve()) or not base.is_dir():
        raise RuntimeError("ORIGINAL_C0_BASELINE_PATH_INVALID")
    signals=json.loads((base/"Signals.json").read_text())
    fills=json.loads((base/"Fills.json").read_text())
    ids={s["signal_id"]:s for s in signals}
    if len(ids)!=len(signals):raise RuntimeError("DUPLICATE_SIGNAL_ID")
    fills=sorted(fills,key=lambda f:instant(f["fill_time_utc"]))
    for f in fills:
        if f["signal_id"] not in ids:raise RuntimeError("ORPHAN_NATIVE_FILL")
        if instant(f["fill_time_utc"])!=instant(ids[f["signal_id"]]["candle_close_time_utc"])+timedelta(milliseconds=1):
            raise RuntimeError("FUTURE_OR_NON_NATIVE_FILL")
    cashpos=[];qty={};k=0
    first_at={str(c):None for c in CUTS}
    first_nonzero_balance_at={str(c):None for c in CUTS}
    hours_by_threshold={str(c):{"hours":0,"hours_with_nonzero_coin_balance":0,"hours_without_nonzero_coin_balance":0} for c in CUTS}
    last_t=None;peak=START;peak_snapshot=None;deepest=None;max_dd=D(0)
    curve_len=0
    with gzip.open(base/"Equity.csv.gz","rt",encoding="utf-8-sig") as h:
        reader=csv.DictReader(h)
        if set(reader.fieldnames or [])!={"time_utc","equity","cash","position_value"}:
            raise RuntimeError("C0_EQUITY_HEADER_UNEXPECTED")
        for curve in reader:
            at=instant(curve["time_utc"])
            if last_t and at-last_t!=timedelta(hours=1):
                raise RuntimeError("C0_NONCONTIGUOUS_HOURLY_LEDGER")
            last_t=at
            equity=decimal(curve["equity"]);cash=decimal(curve["cash"]);pos=decimal(curve["position_value"])
            if equity!=cash+pos:raise RuntimeError("C0_EQUITY_CASH_POS_UNBALANCED")
            if min(equity,cash,pos)<0:raise RuntimeError("C0_NEGATIVE_MONEY")
            while k<len(fills) and instant(fills[k]["fill_time_utc"])<=at:
                fill=fills[k];sig=ids[fill["signal_id"]]
                symbol=sig["symbol"];amount=decimal(fill["base_quantity"])
                if amount<=0:raise RuntimeError("C0_FILL_NONPOSITIVE_QTY")
                prev=qty.get(symbol,D(0))
                if fill["action"]=="ENTER_LONG":qty[symbol]=prev+amount
                elif fill["action"]=="EXIT_LONG":
                    remaining=prev-amount
                    if remaining<D("-0.000000001"):raise RuntimeError("C0_EXIT_WITHOUT_HELD_QUANTITY:"+symbol)
                    qty[symbol]=max(D(0),remaining)
                else:raise RuntimeError("C0_UNKNOWN_FILL_SIDE")
                k+=1
            if equity>peak:
                peak=equity
                peak_snapshot=holdings_snapshot(at,curve,qty,peak,D(0))
            dd=(peak-equity)/peak if peak>0 else D(0)
            snap=None
            for cut in CUTS:
                field=str(cut)
                if dd>=cut:
                    if snap is None:snap=holdings_snapshot(at,curve,qty,peak,dd)
                    if first_at[field] is None:first_at[field]=snap
                    if first_nonzero_balance_at[field] is None and snap["nonzero_balance_symbols_including_possible_dust"]:first_nonzero_balance_at[field]=snap
                    hours_by_threshold[field]["hours"]+=1
                    hours_by_threshold[field]["hours_with_nonzero_coin_balance" if snap["nonzero_balance_symbols_including_possible_dust"] else "hours_without_nonzero_coin_balance"]+=1
            if dd>max_dd:
                max_dd=dd
                deepest=holdings_snapshot(at,curve,qty,peak,dd)
                deepest["preceding_cumulative_HWM_peak"]=peak_snapshot
            curve_len+=1
    if k!=len(fills):raise RuntimeError("UNPROCESSED_NATIVE_FILL")
    return {"window":window,"cost":cost,"source_branch":"frozen owner original archive",
            "scope":"historical C0 closed-bar equity and remaining filled coin balances including possible nontradable dust; native regular positions and slots NOT established",
            "total_hours":curve_len,"total_fills":len(fills),"final_equity_usdc":str(equity),
            "deepest_hwm_drawdown_pct":str(max_dd*D(100)),
            "deepest_drawdown_nonzero_coin_balances_unverified_as_native_positions":deepest,
            "first_at_portfolio_dd_threshold":first_at,
            "first_at_threshold_with_any_nonzero_coin_balance_including_dust":first_nonzero_balance_at,
            "hours_spent_at_drawdown_thresholds":hours_by_threshold,
            "no_new_strategy_financial_backtest":True,
            "feature_time_availability_limit":"Positive quantities from executed fills do NOT prove that a native regular tradable position remains held. MUST reconstruct native position/dust/slot events and OHLC EMA72/ATR24, native costbasis and pending order reservations before treating S01 warning as present."}

def main(bundle,out):
    bundle=pathlib.Path(bundle).resolve(strict=True)
    contract=json.loads((bundle/"Input-Contract.json").read_text())
    if contract.get("source_commit")!=FROZEN:
        raise RuntimeError("FROZEN_SOURCE_COMMIT_MISMATCH")
    checks={}
    for window in WINDOWS:
        for cost in COSTS:
            case=window+"__"+cost
            checks[case]=inspect_case(bundle,window,cost,contract)
            print("NATIVE_C0_EXPOSURE_CASE",json.dumps({"case":case,
                   "hours":checks[case]["total_hours"],
                   "first_dd15_nonzero_coin_balance_including_dust":checks[case]["first_at_threshold_with_any_nonzero_coin_balance_including_dust"].get("0.15") is not None,
                   "max_dd_nonzero_coin_balances_including_dust":checks[case]["deepest_drawdown_nonzero_coin_balances_unverified_as_native_positions"]["nonzero_balance_symbols_including_possible_dust"]}),flush=True)
    result={"status":"C0_FILLED_BALANCE_EXPOSURE_ONLY_SLOT_NOT_VERIFIED",
        "frozen_product":FROZEN,"case_count":len(checks),
        "all_historical_windows_overlap":True,
        "not_a_historical_OOS_test":True,
        "no_new_strategy_simulation":True,
        "cases":checks}
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("HISTORICAL_C0_EXPOSURE_SUMMARY",json.dumps({"status":result["status"],
         "cases":len(checks),"hours":sum(x["total_hours"] for x in checks.values())}),flush=True)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();main(a.bundle,a.output)

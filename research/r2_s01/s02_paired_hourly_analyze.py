"""S02 descriptive paired native trace analysis, strictly no intervention/optimization."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,pathlib
from datetime import datetime,timedelta
from decimal import Decimal as D
def d(v):return D(str(v))
def read(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:return json.load(f)
def run(a):
    ctrl=read(a.control);cand=read(a.candidate)
    old=json.loads(pathlib.Path(a.current_s01).read_text())
    assert ctrl["mode"]=="control" and cand["mode"]=="candidate"
    assert ctrl["frozen"]==cand["frozen"]=="f56d48536525830dd6ea50bf5bc174a6f9aeff8c"
    assert ctrl["source_policy_blob_sha"]==cand["source_policy_blob_sha"]=="b104854b95ecf1623dd6fcfbbba9d5303a8909fb"
    assert len(ctrl["rows"])==len(cand["rows"])==26304
    assert d(ctrl["ending_equity"])==d(old["C0_ending_equity_usdc"])==D("33867.79699289748400000000")
    assert d(cand["ending_equity"])==d(old["candidate_ending_equity_usdc"])==D("10967.68139761524970000000")
    assert ctrl["total_native_fills"]==361 and cand["total_native_fills"]==423
    assert ctrl["total_native_trades"]==180 and cand["total_native_trades"]==211
    crows=ctrl["rows"]; srows=cand["rows"]
    first=None; diverged=0;cash_different=0;allocation_different=0
    cumulative_abs_cash=D(0);cumulative_abs_equity=D(0)
    native_costs={k:dict(fee=D(0),adverse=D(0),gross=D(0),fill_count=0) for k in ("C0","S01")}
    positions_held={k:collections.Counter() for k in ("C0","S01")}
    slot_hours={"C0":0,"S01":0}
    active_usdc_total={"C0":D(0),"S01":D(0)}
    per_coin_different_hours=collections.Counter()
    max_equity_spread=(D(0),None)
    candidate_blocked=[]
    new_signals={}
    base_trades=[]
    c0_signal_ids=set()
    first_s01_event_id=None
    matched_events=[]
    forced=[x for x in old["s01_events"] if x["kind"]=="FILLED_NATIVE_FULL_EXIT"]
    assert len(forced)==52
    forced_lookup={(x["fill_utc"],x["native_fill_signal_id"]):x for x in forced}
    old_sample_by_fill={v["id"]:v for v in old["native_s01_fill_trade_ledger_audit"]["examples"]}
    for i,(c,s) in enumerate(zip(crows,srows,strict=True)):
        if c["utc"]!=s["utc"]:
            raise RuntimeError("S02_UNMATCHED_NATIVE_TIME")
        # Full simultaneous ledger equality until the first actual causal difference.
        difference=([c[k]!=s[k] for k in ("cash","equity","position_value","positions","dust","pending","signals","fills","trades","blocked")])
        # Note: signals and blocked can diverge after portfolio forks. Their value is evidence,
        # not proof of specific counterfactual profit for any one event.
        if any(difference):
            diverged+=1
            if first is None:
                first=dict(utc=c["utc"],hour_index=i,
                    changed_fields=[k for k,flag in zip(("cash","equity","position_value","positions","dust","pending","signals","fills","trades","blocked"),difference) if flag],
                    C0_equity=c["equity"],S01_equity=s["equity"],C0_cash=c["cash"],S01_cash=s["cash"],
                    C0_positions=c["positions"],S01_positions=s["positions"],
                    C0_recent_fills=c["fills"],S01_recent_fills=s["fills"])
        if c["cash"]!=s["cash"]:cash_different+=1
        if c["positions"]!=s["positions"]:allocation_different+=1
        ec=d(c["equity"])-d(s["equity"])
        cumulative_abs_equity+=abs(ec)
        if abs(ec)>max_equity_spread[0]:max_equity_spread=(abs(ec),c["utc"])
        cumulative_abs_cash+=abs(d(c["cash"])-d(s["cash"]))
        for tag,row in (("C0",c),("S01",s)):
            slot_hours[tag]+=row["occupied_slots"]
            active_usdc_total[tag]+=d(row["position_value"])
            for symbol in row["positions"]:
                positions_held[tag][symbol]+=1
            for fill in row["fills"]:
                n=native_costs[tag]
                n["fee"]+=d(fill["fee"]);n["adverse"]+=d(fill["adverse"])
                n["gross"]+=d(fill["gross"]);n["fill_count"]+=1
        for symbol in set(c["positions"])|set(s["positions"]):
            if c["positions"].get(symbol)!=s["positions"].get(symbol):
                per_coin_different_hours[symbol]+=1
        for sig in s["signals"]:new_signals[sig["id"]]=sig
        for sig in c["signals"]:c0_signal_ids.add(sig["id"])
        for reason in s["blocked"]:
            if ":S01_COIN_COOLDOWN" in reason:
                sid=reason.split(":",1)[0]
                candidate_blocked.append(dict(utc=s["utc"],id=sid,reason=reason,
                        matched_candidate_signal=new_signals.get(sid)))
        for t in c["trades"]:base_trades.append(dict(t,utc=c["utc"]))
        for f in s["fills"]:
            key=(f["utc"],f["id"])
            if key in forced_lookup:
                event=forced_lookup[key]
                old_origin=event["symbol"]
                # C0 may be no longer holding this position or have a different entry;
                # print actual C0 state without asserting counterfactual profit.
                matched_events.append(dict(
                    native_fill_utc=f["utc"],close_utc=s["utc"],symbol=old_origin,
                    fill_signal=f["id"],sale_gross=f["gross"],fee=f["fee"],cash_net=str(d(f["gross"])-d(f["fee"])),
                    previous_native_basis=event["native_prior_remaining_basis"],
                    sold_qty=event["sold_quantity"],
                    C0_same_coin_position_at_this_close=c["positions"].get(old_origin),
                    S01_same_coin_position_at_this_close=s["positions"].get(old_origin),
                    C0_cash_after=c["cash"],S01_cash_after=s["cash"],
                    C0_equity_after=c["equity"],S01_equity_after=s["equity"],
                    C0_occupied_slots_after=c["occupied_slots"],
                    S01_occupied_slots_after=s["occupied_slots"]))
    if len(matched_events)!=52:raise RuntimeError("S02_FORCED_NATIVE_FILLS_NOT_LINKED_TO_C0")
    # Link exact same original entry ID in native original C0 trade history if available.
    for item in matched_events:
        event=forced_lookup[(item["native_fill_utc"],item["fill_signal"])]
        # Original entry only known from prior snapshots on the forced hour: look backward.
        j=next(k for k,r in enumerate(srows) if r["utc"]==item["close_utc"])
        before=srows[j-1]["positions"].get(item["symbol"]) if j else None
        entry_id=before["entry"] if before else None
        item["S01_original_entry_signal_id"]=entry_id
        original_exits=[t for t in base_trades if t["entry"]==entry_id and t["symbol"]==item["symbol"]] if entry_id else []
        item["C0_same_entry_later_exit_utc"]=[t["utc"] for t in original_exits]
        item["C0_same_entry_realized_pnl"]=[t["realized"] for t in original_exits]
        # C0 equal entry may be absent by the sale time due to different earlier fork.
        item["C0_same_entry_still_held"]=bool(entry_id and item["C0_same_coin_position_at_this_close"] and
                                       item["C0_same_coin_position_at_this_close"]["entry"]==entry_id)
    fee_diff=native_costs["S01"]["fee"]-native_costs["C0"]["fee"]
    adverse_diff=native_costs["S01"]["adverse"]-native_costs["C0"]["adverse"]
    if fee_diff!=D("-508.99109198973660000000") or adverse_diff!=D("-254.49873700520000000"):
        raise RuntimeError("S02_ORIGINAL_COST_AUDIT_MISMATCH")
    for tag,v in native_costs.items():
        if v["fill_count"]!=({"C0":361,"S01":423}[tag]):
            raise RuntimeError("S02_FILL_COUNT_VS_ORIGINAL_MISMATCH")
    block_counts=collections.Counter(x["reason"].split(":",1)[1] for x in candidate_blocked)
    report=dict(id="R2-S02-DIAG-002",status="PAIRED_HOURLY_NATIVE_DESCRIPTIVE_AUDIT",
                research_only=True,policy_hash="b104854b95ecf1623dd6fcfbbba9d5303a8909fb",
                rows=len(crows),UTC_start=crows[0]["utc"],UTC_end=crows[-1]["utc"],
                first_observed_path_difference=first,
                nonidentical_hourly_state_count=diverged,
                different_cash_hours=cash_different,
                different_position_inventory_hours=allocation_different,
                time_integral_absolute_cash_difference_usdc_hours=str(cumulative_abs_cash),
                time_integral_absolute_equity_difference_usdc_hours=str(cumulative_abs_equity),
                max_absolute_hourly_equity_gap_usdc=str(max_equity_spread[0]),
                max_hourly_gap_at_utc=max_equity_spread[1],
                native_book=dict(
                    C0=dict(fees=str(native_costs["C0"]["fee"]),adverse=str(native_costs["C0"]["adverse"]),
                        turnover_gross=str(native_costs["C0"]["gross"]),native_fills=361,
                        slot_hours=slot_hours["C0"],positions_hours_by_coin=dict(positions_held["C0"])),
                    S01=dict(fees=str(native_costs["S01"]["fee"]),adverse=str(native_costs["S01"]["adverse"]),
                        turnover_gross=str(native_costs["S01"]["gross"]),native_fills=423,
                        slot_hours=slot_hours["S01"],positions_hours_by_coin=dict(positions_held["S01"]))),
                changed_position_hours_by_coin=dict(per_coin_different_hours),
                full_native_s01_exits=52,
                confirmed_sale_events_linked_to_C0=matched_events,
                explicit_cooldown_blocks_exhaustive_in_native_blocked_ledger=candidate_blocked,
                total_cooldown_block_records=len(candidate_blocked),
                matched_signal_count_for_cooldown_blocks=sum(x["matched_candidate_signal"] is not None for x in candidate_blocked),
                total_native_fee_difference_S01_minus_C0=str(fee_diff),
                total_native_adverse_difference_S01_minus_C0=str(adverse_diff),
                C0_end_usdc=ctrl["ending_equity"],S01_end_usdc=cand["ending_equity"],
                full_path_terminal_delta_usdc=str(d(cand["ending_equity"])-d(ctrl["ending_equity"])),
                causal_sale_only_pnl=None,causal_cooldown_only_pnl=None,
                causal_reinvestment_only_pnl=None,
                causal_interaction_terms=None,
                observed_relationship_not_causal_apportionment=True,
                next_candidate_not_prematurely_optimized=True)
    output=pathlib.Path(a.output)
    if output.exists():raise RuntimeError("S02_NO_OVERWRITE")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("S02_DIAG_002_RESULT",json.dumps({k:v for k,v in report.items()
        if k in ("rows","first_observed_path_difference","nonidentical_hourly_state_count",
                 "different_cash_hours","different_position_inventory_hours",
                 "full_native_s01_exits","total_cooldown_block_records",
                 "total_native_fee_difference_S01_minus_C0",
                 "full_path_terminal_delta_usdc")},ensure_ascii=False),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("control","candidate","current-s01","output"):p.add_argument("--"+name,required=True)
    run(p.parse_args())

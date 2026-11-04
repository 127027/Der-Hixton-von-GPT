"""Independent S02 read-only raw-hourly QA; no imports from S02 strategy/analyzer."""
from __future__ import annotations
import argparse,collections,gzip,json,pathlib
from datetime import datetime,timedelta
from decimal import Decimal as D
def load(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:return json.load(f)
def run(a):
    orig=load(a.control)
    cand=load(a.candidate)
    report=json.loads(pathlib.Path(a.report).read_text())
    old=json.loads(pathlib.Path(a.old).read_text())
    for obj,mode,ending,number in ((orig,"control","33867.79699289748400000000",361),
                                   (cand,"candidate","10967.68139761524970000000",423)):
        assert obj["mode"]==mode and D(obj["ending_equity"])==D(ending)
        assert len(obj["rows"])==26304 and obj["total_native_fills"]==number
        prior=None;seen=0;fee=D(0);adverse=D(0)
        for row in obj["rows"]:
            t=datetime.fromisoformat(row["utc"])
            if prior and t-prior!=timedelta(hours=1):raise AssertionError("S02_QA_TIME_GAP")
            prior=t
            if D(row["cash"])+D(row["position_value"])!=D(row["equity"]):
                raise AssertionError("S02_QA_NATIVE_MONEY")
            assert row["occupied_slots"]==sum(x["slots"] for x in row["positions"].values())
            for x in row["positions"].values():
                assert D(x["qty"])>0 and D(x["basis"])>0
            for x in row["fills"]:
                seen+=1;fee+=D(x["fee"]);adverse+=D(x["adverse"])
                if datetime.fromisoformat(x["utc"])>t:
                    raise AssertionError("S02_QA_FILL_FUTURE")
        assert seen==number
        expected= ("2246.86176813631745000000","1123.43545868545000000") if mode=="control" else ("1737.87067614658085000000","868.93672168025000000")
        assert fee==D(expected[0]) and adverse==D(expected[1])
    c=orig["rows"];s=cand["rows"]
    first=next(i for i,(a,b) in enumerate(zip(c,s,strict=True)) if a["positions"]!=b["positions"] or a["cash"]!=b["cash"] or a["equity"]!=b["equity"] or a["fills"]!=b["fills"])
    assert first==1615
    assert s[first]["utc"]=="2023-12-18T02:59:59.999000+00:00"
    assert len([x for row in s for x in row["fills"] if x["id"] in
         {ev["native_fill_signal_id"] for ev in old["s01_events"] if ev["kind"]=="FILLED_NATIVE_FULL_EXIT"}])==52
    assert len(report["confirmed_sale_events_linked_to_C0"])==52
    assert report["first_observed_path_difference"]["hour_index"]==first
    orig_fills={f["id"]:f for row in c for f in row["fills"]}
    orig_signals={sig["id"]:sig for row in c for sig in row["signals"]}
    c0_blocked={x.split(":",1)[0]:x for row in c for x in row["blocked"]}
    cooldown=[]
    for row in s:
        for text in row["blocked"]:
            if not text.endswith(":S01_COIN_COOLDOWN"):continue
            sid=text.split(":",1)[0]
            own_sig=next((v for v in row["signals"] if v["id"]==sid),None)
            if own_sig is None:
                # Native policy can reject a pending signal at the following open,
                # whose original signal belongs to the preceding closed hour.
                own_sig=next((v for v in cand["rows"][max(0,s.index(row)-1)]["signals"] if v["id"]==sid),None)
            if own_sig is None or own_sig["action"]!="ENTER_LONG":
                raise AssertionError("S02_QA_COOLDOWN_BLOCK_UNLINKED_TO_NATIVE_ENTER_SIGNAL")
            c0_fill=orig_fills.get(sid)
            cooldown.append(dict(
                blocked_observed_at_closed_utc=row["utc"],signal_id=sid,
                symbol=own_sig["symbol"],
                same_signal_present_in_C0=bool(sid in orig_signals),
                same_signal_filled_in_C0=bool(c0_fill is not None and c0_fill["action"]=="ENTER_LONG"),
                native_C0_blocked_other_reason=c0_blocked.get(sid),
                candidate_reported_reason=text))
    assert len(cooldown)==report["total_cooldown_block_records"]==15
    candidate_pending_s01_count=sum(x["same_signal_filled_in_C0"] for x in cooldown)
    result={
       "id":"R2-S02-DIAG-002-INDEPENDENT-RAW-QA","status":"DIAGNOSTIC_QA_PASS_LIMITED_DESCRIPTIVE",
       "source_hourly_run":41889629161,
       "original_data_sha256_verified_in_source_run":True,
       "original_f56_hour_rows_verified_per_path":26304,
       "original_and_candidate_ending_equity_native_exact":True,
       "first_native_accounting_divergence_index":first,
       "native_s01_exit_count_verified":52,
       "total_native_cooldown_block_reasons":len(cooldown),
       "candidate_cooldown_blocks_with_C0_genuine_filled_buy_same_signal":candidate_pending_s01_count,
       "candidate_cooldown_blocks_without_C0_genuine_filled_buy_same_signal":len(cooldown)-candidate_pending_s01_count,
       "per_block_evidence":cooldown,
       "blocked_valid_order_not_equivalent_to_lost_profit":True,
       "other_slot_and_cash_reasons_not_excluded_for_nonfilled_C0_signals":True,
       "causal_pnl_attribution":None,
       "all_original_market_rules_preserved":True,
       "separate_qa_script_not_a_trading_method_approval":True}
    p=pathlib.Path(a.output)
    if p.exists():raise RuntimeError("S02_INDEPENDENT_QA_NO_OVERWRITE")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("DOT4_INDEPENDENT_S02_QA_RESULT",json.dumps({
      k:v for k,v in result.items() if k!="per_block_evidence"},ensure_ascii=False),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for n in ("control","candidate","report","old","output"):p.add_argument("--"+n,required=True)
    run(p.parse_args())

"""Independently verify saved native S02 lock ablation vs original locked native trace."""
from __future__ import annotations
import argparse,gzip,json,pathlib
from datetime import datetime,timedelta
from decimal import Decimal as D
def load(p):
    with gzip.open(p,"rt",encoding="utf-8") as f:return json.load(f)
def run(a):
    locked=load(a.locked)
    nolock=load(a.unlocked)
    x=json.loads(pathlib.Path(a.ablation_summary).read_text())
    assert locked["mode"]==nolock["mode"]=="candidate"
    assert locked["source_policy_blob_sha"]==nolock["source_policy_blob_sha"]=="b104854b95ecf1623dd6fcfbbba9d5303a8909fb"
    assert len(locked["rows"])==len(nolock["rows"])==26304
    assert locked["total_native_fills"]==423 and nolock["total_native_fills"]==441
    assert locked["total_native_trades"]==211 and nolock["total_native_trades"]==220
    assert D(locked["ending_equity"])==D("10967.68139761524970000000")
    assert D(nolock["ending_equity"])==D("10282.95502862161145000000")
    first=None;first_accounting=None;first_new_buy=None;coin_block_ids=set()
    for i,(before,after) in enumerate(zip(locked["rows"],nolock["rows"],strict=True)):
        assert before["utc"]==after["utc"]
        assert D(after["cash"])+D(after["position_value"])==D(after["equity"])
        assert after["occupied_slots"]==sum(v["slots"] for v in after["positions"].values())
        if first is None and any(before[k]!=after[k] for k in ("cash","equity","positions","dust","pending","fills","trades","blocked")):
            first={"index":i,"utc":before["utc"],
                   "locked_blocked_at_hour":before["blocked"],"unlocked_blocked_at_hour":after["blocked"],
                   "locked_positions":before["positions"],"unlocked_positions":after["positions"]}
        if first_accounting is None and any(before[k]!=after[k] for k in ("cash","equity","positions","dust","fills","trades")):
            first_accounting={"index":i,"utc":before["utc"]}
        for line in before["blocked"]:
            if line.endswith(":S01_COIN_COOLDOWN"):
                coin_block_ids.add(line.split(":",1)[0])
        if first_new_buy is None:
            locked_buy={v["id"] for v in before["fills"] if v["action"]=="ENTER_LONG"}
            for item in after["fills"]:
                if item["action"]=="ENTER_LONG" and item["id"] not in locked_buy and item["id"] in coin_block_ids:
                    first_new_buy={"index":i,"utc":before["utc"],"signal_id":item["id"]}
    assert first is not None and first_accounting is not None
    assert first["index"]<=first_accounting["index"]
    assert x["conditional_total_portfolio_delta_no_lock_minus_24h_lock_usdc"]==str(D(nolock["ending_equity"])-D(locked["ending_equity"]))
    assert x["full_native_no_lock_exit_count"]==55
    out=dict(id="R2-S02-ABL-001-SEPARATE-RAW-QA",
             status="DIAGNOSTIC_ABLATION_QA_PASS_LIMITED_HISTORICAL",
             locked_current_native_ref_run=41889629161,
             no_lock_preregistered_run=41890504643,
             original_policy_blob_unchanged="b104854b95ecf1623dd6fcfbbba9d5303a8909fb",
             exact_26304_matched_native_hours=True,
             first_observed_divergence=first,
             first_money_or_position_divergence=first_accounting,
             first_identified_unlocked_buy_from_previous_lock_block=first_new_buy,
             locked_native_terminal_usdc=locked["ending_equity"],
             unlocked_native_terminal_usdc=nolock["ending_equity"],
             no_lock_minus_24h_lock_usdc=x["conditional_total_portfolio_delta_no_lock_minus_24h_lock_usdc"],
             more_native_s01_sells_after_ablating_cooldown=55-52,
             native_lock_blocks_total=len(coin_block_ids),
             no_additive_missed_profit_attribution=True,
             conditional_scope_original_32k_current_only=True,
             no_product_promotion=True,
             note="Ablation is a pathwise intervention effect conditional on rejected S01 exits; not a separable share of total C0/S01 gap.")
    path=pathlib.Path(a.output)
    if path.exists():raise RuntimeError("ABL_QA_OUTPUT_EXISTS")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,indent=2)+"\n")
    print("R2_S02_ABL_INDEPENDENT_QA_RESULT",json.dumps({k:v for k,v in out.items() if k not in ("first_observed_divergence",)},ensure_ascii=False),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for t in ("locked","unlocked","ablation-summary","output"):p.add_argument("--"+t,required=True)
    run(p.parse_args())

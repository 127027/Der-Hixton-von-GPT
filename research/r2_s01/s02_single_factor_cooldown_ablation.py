"""Read-only controlled S01-A one-factor no-coin-lock ablation.

Does NOT edit S01-A policy source, original f56 or production settings.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys
from datetime import datetime,timedelta
from decimal import Decimal as D
def run(a):
    b=pathlib.Path(a.bundle).resolve(strict=True)
    original_policy=pathlib.Path("research/r2_s01/native_s01_policy.py")
    raw=original_policy.read_bytes()
    git_blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    if git_blob!="b104854b95ecf1623dd6fcfbbba9d5303a8909fb":
        raise RuntimeError("ABL_S01_POLICY_BLOB_DRIFT:"+git_blob)
    from research.r2_hold003.run_native import snapshot_loader
    snapshot_loader(bundle=b,kind="historical",window="original_32k")
    from research.r2_s01.native_s01_policy import S01Policy
    original=S01Policy.entry_allowed
    costs=type("C",(),dict(adverse_price_rate=D("0.001"),fee_rate=D("0.001")))()
    # Before intervention: closed native sale activates a real 24h symbol restriction.
    p=S01Policy(features={},costs=costs)
    at=datetime(2024,1,1)
    p.cooldown_until["BTCUSDC"]=at+timedelta(hours=24)
    if original(p,"BTCUSDC",at+timedelta(hours=1)):
        raise RuntimeError("ABL_ORIGINAL_COIN_LOCK_NOT_ACTIVE")
    def permissive_only_for_s01_additional_coin_lock(self,symbol,at):
        return True
    S01Policy.entry_allowed=permissive_only_for_s01_additional_coin_lock
    if not p.entry_allowed("BTCUSDC",at+timedelta(hours=1)):
        raise RuntimeError("ABL_NO_LOCK_OVERRIDE_NOT_ACTIVE")
    if p.filter_entries([type("Sig",(),dict(symbol="BTCUSDC",signal_id="single-fixture"))()],
                        at+timedelta(hours=1),[])[0].signal_id!="single-fixture":
        raise RuntimeError("ABL_NATIVE_PENDING_COIN_LOCK_NOT_BYPASSED")
    from research.r2_s01.run_native_s01 import run as native_run
    native_args=argparse.Namespace(bundle=str(b),window="original_32k",
        cost="current",mode="candidate",output=a.output,trace=a.trace)
    native_run(native_args)
    x=json.loads(pathlib.Path(a.output).read_text())
    if x["native_s01_fill_trade_ledger_audit"]["status"]!="NATIVE_EVENT_LEDGER_RECONCILED":
        raise RuntimeError("ABL_NATIVE_LEDGER_AUDIT_NOT_PASS")
    previous=json.loads(pathlib.Path(a.original_s01).read_text())
    if D(str(previous["candidate_ending_equity_usdc"]))!=D("10967.68139761524970000000") or previous["s01_executed_count"]!=52:
        raise RuntimeError("ABL_ORIGINAL_S01_ANCHOR_DRIFT")
    result=dict(id="R2-S02-ABL-001",status="DIAGNOSTIC_COUNTERFACTUAL_ONE_VARIABLE_ONLY",
      code_policy_git_blob=git_blob,ablated_element="S01-SPECIFIC_POST_FILL_COIN_BUY_LOCK_ONLY",
      all_original_f56_native_entry_rules_intact=True,
      original_C0_end_usdc=previous["C0_ending_equity_usdc"],
      S01_with_24h_lock_end_usdc=previous["candidate_ending_equity_usdc"],
      S01_without_24h_lock_end_usdc=x["candidate_ending_equity_usdc"],
      conditional_total_portfolio_delta_no_lock_minus_24h_lock_usdc=
        str(D(str(x["candidate_ending_equity_usdc"]))-D(str(previous["candidate_ending_equity_usdc"]))),
      full_native_no_lock_exit_count=x["s01_executed_count"],
      full_native_no_lock_fill_count=x["native_fill_count"],
      full_native_no_lock_trade_count=x["native_trade_count"],
      full_native_no_lock_total_fee_usdc=x["native_total_fees"],
      full_native_no_lock_total_adverse_usdc=x["native_total_spread_slippage"],
      exact_original_native_fill_trade_audit=x["native_s01_fill_trade_ledger_audit"]["status"],
      no_individual_blocked_profit_attribution=True,
      pathwise_compounding_and_trade_interaction_included=True,
      no_strategy_promotion=True)
    path=pathlib.Path(a.summary)
    if path.exists():raise RuntimeError("ABL_NO_OVERWRITE")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+"\n")
    print("R2_S02_ABL_001_RESULT",json.dumps(result),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for item in ("bundle","original-s01","output","summary"):p.add_argument("--"+item,required=True)
    p.add_argument("--trace",default=None)
    run(p.parse_args())

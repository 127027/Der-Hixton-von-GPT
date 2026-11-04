"""R2-S02-DIAG-001: read existing S01 and C0 artifacts; no financial replay.

This is a deliberately NON-causal descriptive mechanism audit.
"""
from __future__ import annotations
from collections import Counter
from decimal import Decimal as D
import argparse,json,pathlib

def run(args):
    source=pathlib.Path(args.artifact).resolve(strict=True)
    bundle=pathlib.Path(args.bundle).resolve(strict=True)
    out=pathlib.Path(args.output)
    if out.exists():raise RuntimeError("DIAG_NO_OVERWRITE")
    x=json.loads(source.read_text())
    assert x["id"]=="R2-D3-S01" and x["mode"]=="candidate"
    assert x["window"]=="original_32k" and x["cost"]=="current"
    assert x["native_s01_fill_trade_ledger_audit"]["status"]=="NATIVE_EVENT_LEDGER_RECONCILED"
    contract=json.loads((bundle/"Input-Contract.json").read_text())
    p=bundle/contract["windows"]["original_32k"]["baseline"]["current"]["path"]
    original_fills=json.loads((p/"Fills.json").read_text())
    original_trades=json.loads((p/"Trades.json").read_text())
    original_metrics=json.loads((p/"Result.json").read_text())["metrics"]
    events=x["s01_events"]
    counts=Counter(y["kind"] for y in events)
    sold=[y for y in events if y["kind"]=="FILLED_NATIVE_FULL_EXIT"]
    assert len(sold)==x["s01_executed_count"]==x["native_s01_fill_trade_ledger_audit"]["native_confirmed_s01_exits"]
    by_symbol=Counter(y["symbol"] for y in sold)
    sum_field=lambda key:sum((D(str(y[key])) for y in sold),D(0))
    fees0=sum((D(str(f["fee_quote_equivalent"])) for f in original_fills),D(0))
    fees1=D(str(x["native_total_fees"]))
    spread0=sum((D(str(f["modeled_spread_slippage"])) for f in original_fills),D(0))
    spread1=D(str(x["native_total_spread_slippage"]))
    end0=D(str(original_metrics["ending_equity"]))
    end1=D(str(x["candidate_ending_equity_usdc"]))
    assert end0==D(str(x["C0_ending_equity_usdc"]))
    result={
      "id":"R2-S02-DIAG-001","source_run_id":41873929231,
      "context":"original_32k__current",
      "status":"DESCRIPTIVE_NATIVE_ARTIFACT_MEASUREMENT_ONLY",
      "frozen_f56":contract["source_commit"],
      "starting_usdc":str(x["starting_equity_usdc"]),
      "C0_end_usdc":str(end0),"S01_end_usdc":str(end1),
      "full_path_terminal_delta_usdc":str(end1-end0),
      "confirmed_s01_native_full_exits":len(sold),
      "native_regular_exit_takeovers":counts.get("SKIPPED_REGULAR_EXIT",0),
      "native_rejected_or_dust_no_fills":counts.get("REJECTED_OR_DUST_NO_FILL",0),
      "unknown_native_state":counts.get("UNKNOWN_NATIVE_EXECUTION",0),
      "event_counts":dict(counts),
      "s01_exits_by_symbol":dict(sorted(by_symbol.items())),
      "s01_confirmed_sale_quote_gross_usdc":str(sum_field("native_quote_value")),
      "s01_confirmed_sale_fee_usdc":str(sum_field("native_fee_quote")),
      "s01_confirmed_sale_net_cash_flow_usdc":str(sum_field("native_net_cash_delta")),
      "s01_slot_release_event_total_NOT_UNIQUE_SLOTS":sum(y["freed_native_slots"] for y in sold),
      "observed_cooldown_blocked_entry_events_LOWER_BOUND":counts.get("BLOCKED_ENTRY_COIN_COOLDOWN",0),
      "C0_all_native_fill_count":len(original_fills),
      "S01_all_native_fill_count":x["native_fill_count"],
      "native_fill_count_delta":x["native_fill_count"]-len(original_fills),
      "C0_closed_trade_count":len(original_trades),
      "S01_closed_trade_count":x["native_trade_count"],
      "C0_total_fee_usdc":str(fees0),
      "S01_total_fee_usdc":str(fees1),
      "all_native_fee_delta_S01_minus_C0_usdc":str(fees1-fees0),
      "C0_total_modeled_adverse_usdc":str(spread0),
      "S01_total_modeled_adverse_usdc":str(spread1),
      "all_native_adverse_delta_S01_minus_C0_usdc":str(spread1-spread0),
      "candidate_has_no_exported_complete_hourly_cash_or_positions":True,
      "cooldown_event_count_not_complete_due_to_nonlogged_next_pending_blocks":True,
      "causal_premature_exit_pnl_usdc":None,
      "causal_cooldown_pnl_usdc":None,
      "causal_other_coin_reallocation_pnl_usdc":None,
      "causal_compounding_pnl_usdc":None,
      "trade_level_cost_attribution_usdc":None,
      "interpretation":"The total terminal equity delta is path-dependent; sale proceeds and fee totals are not additive explanations of missed opportunities.",
      "live_and_product_unchanged":True
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("R2_S02_CAUSAL_DIAG_DESCRIPTIVE",json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--artifact",required=True)
    p.add_argument("--bundle",required=True)
    p.add_argument("--output",required=True)
    run(p.parse_args())

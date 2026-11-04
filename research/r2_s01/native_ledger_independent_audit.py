"""Evidence-only S01 native financial ledger audit independent of S01 policy module.

This checks original Fill/Trade objects after the real f56 native engine has run;
it is NOT an external reviewer or independent human signoff.
"""
from __future__ import annotations
from collections import Counter
from decimal import Decimal as D
from datetime import timedelta
from hixton.domain.models import SignalAction


def audit_s01_native_result(*, result, policy, costs):
    fill_by_id={}
    trade_by_id={}
    for fill in result.fills:
        fill_by_id.setdefault(fill.signal_id,[]).append(fill)
    for trade in result.trades:
        trade_by_id.setdefault(trade.exit_signal_id,[]).append(trade)
    sig_by_id={s.signal_id:s for s in result.signals}
    if len(sig_by_id)!=len(result.signals):
        raise RuntimeError("S01_AUDIT_DUPLICATE_NATIVE_SIGNALS")
    counts=Counter()
    details=[]
    for event in policy.events:
        kind=event["kind"]
        counts[kind]+=1
        if kind=="UNKNOWN_NATIVE_EXECUTION":
            raise RuntimeError("S01_AUDIT_UNRESOLVED_NATIVE_EXECUTION")
        if kind=="FILLED_NATIVE_FULL_EXIT":
            ident=event["native_fill_signal_id"]
            ff=fill_by_id.get(ident,[])
            tt=trade_by_id.get(ident,[])
            if len(ff)!=1 or len(tt)!=1 or ident not in sig_by_id:
                raise RuntimeError("S01_AUDIT_MISSING_OR_DUPLICATED_FILL_TRADE_SIGNAL")
            f,t,s=ff[0],tt[0],sig_by_id[ident]
            if f.action is not SignalAction.EXIT_LONG or s.action is not SignalAction.EXIT_LONG:
                raise RuntimeError("S01_AUDIT_WRONG_ACTION")
            if f.fill_time_utc!=s.candle_close_time_utc+timedelta(milliseconds=1):
                raise RuntimeError("S01_AUDIT_NON_NATIVE_FILL_TIMING")
            if f.fill_time_utc.isoformat()!=event["fill_utc"]:
                raise RuntimeError("S01_AUDIT_EVENT_TIME_MISMATCH")
            net=f.quote_value-f.fee_quote_equivalent
            if f.base_quantity!=D(event["sold_quantity"]) or net!=D(event["native_net_cash_delta"]):
                raise RuntimeError("S01_AUDIT_NATIVE_LEDGER_EVENT_MISMATCH")
            if f.fee_quote_equivalent!=f.quote_value*costs.fee_rate:
                raise RuntimeError("S01_AUDIT_NON_NATIVE_FEE")
            if t.exit_quote_receive!=net or t.realized_pnl!=net-t.entry_quote_spend:
                raise RuntimeError("S01_AUDIT_TRADE_BASIS_OR_PNL_WRONG")
            prior_qty=D(event["estimated_prior_held_quantity"])
            prior_basis=D(event["native_prior_remaining_basis"])
            if prior_qty<=0 or prior_basis<=0 or f.base_quantity>prior_qty:
                raise RuntimeError("S01_AUDIT_BAD_PRE_EXIT_POSITION")
            expected_basis=prior_basis*(f.base_quantity/prior_qty)
            if expected_basis!=t.entry_quote_spend:
                raise RuntimeError("S01_AUDIT_PROPORTIONAL_NATIVE_BASIS_MISMATCH")
            if t.sold_base_quantity!=f.base_quantity or t.slot_count!=event["freed_native_slots"]:
                raise RuntimeError("S01_AUDIT_SLOT_OR_QUANTITY_MISMATCH")
            expected_dust=prior_qty-f.base_quantity
            if t.residual_dust_quantity!=expected_dust:
                raise RuntimeError("S01_AUDIT_DUST_CONSERVATION_MISMATCH")
            details.append({"id":ident,"symbol":t.symbol,"fill_utc":event["fill_utc"],
                "sold":str(f.base_quantity),"net_cash":str(net),
                "native_fee_quote":str(f.fee_quote_equivalent),
                "native_basis":str(t.entry_quote_spend),
                "realized_pnl":str(t.realized_pnl),
                "native_residual_dust":str(t.residual_dust_quantity),
                "released_slots":event["freed_native_slots"]})
        elif kind=="REJECTED_OR_DUST_NO_FILL":
            if event.get("cooldown_activated") is not False or not event.get("native_rejections"):
                raise RuntimeError("S01_AUDIT_REJECTION_UNPROVEN_OR_COOLDOWN")
        elif kind=="SKIPPED_REGULAR_EXIT":
            if not event["symbol"]:
                raise RuntimeError("S01_AUDIT_REGULAR_EXIT_NO_SYMBOL")
    if counts["FILLED_NATIVE_FULL_EXIT"]!=len(details):
        raise RuntimeError("S01_AUDIT_EXIT_COUNT")
    return {"status":"NATIVE_EVENT_LEDGER_RECONCILED", "native_confirmed_s01_exits":len(details),
            "events":dict(counts),"examples":details[:25],
            "partial_exchange_fills_covered":False}

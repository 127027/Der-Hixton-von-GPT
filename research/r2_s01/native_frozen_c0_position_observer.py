"""Read-only S01 precursor diagnostic with genuine f56 active positions, not dust.

One original C0 control replay is instrumented solely for observing state. The
instrumented replay MUST match frozen C0 metrics, fills, signals, trades and
each hourly cash/equity record exactly, else fail-closed. No candidate trades.
Historical data are development, NOT OOS.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,pathlib,runpy,sys,types
from datetime import datetime,timedelta
from decimal import Decimal as D,ROUND_DOWN
from research.r2_hold003.run_native import snapshot_loader,assert_native,digest,FROZEN_NATIVE_PORTFOLIO_SHA,FROZEN
# Native engine is injected only after verifying and loading frozen original archive.
ONE=D(1)
ZERO=D(0)

def dec(x):
    v=D(str(x))
    if not v.is_finite():raise RuntimeError("NONFINITE_INPUT")
    return v

def s01_features_from_closed_candles(data):
    """Prefix-invariant EMA72, seeded by SMA of first 72 original closed bars."""
    alpha=D(2)/D(73)
    all_features={}
    for sym,series in data.items():
        closes=[]
        features={}
        ema=None
        mask=collections.deque(maxlen=6)
        last=None
        for candle in series:
            if not candle.closed:raise RuntimeError("UNCLOSED_INPUT:"+sym)
            t=candle.close_time_utc
            if last and t-last!=timedelta(hours=1):raise RuntimeError("NONCONTIGUOUS_OHLC:"+sym)
            last=t
            close=dec(candle.close)
            if close<=0:raise RuntimeError("NONPOSITIVE_CLOSE:"+sym)
            closes.append(close)
            if len(closes)==72:ema=sum(closes,D(0))/D(72)
            elif len(closes)>72:ema=alpha*close+(ONE-alpha)*ema
            if ema is not None:
                mask.append(int(close<ema))
                if len(mask)==6:
                    features[t]=(close,ema,sum(mask))
        all_features[sym]=features
    return all_features

class PositionObserver:
    """No state mutation, no orders, no strategy signal injection."""
    def __init__(self,feature_cache,costs,window,cost):
        self.f=feature_cache;self.costs=costs;self.window=window;self.cost=cost
        self.total_hours=0;self.sample_count_with_regular=0
        self.sample_count_with_only_dust=0;self.sample_count_with_no_balances=0
        self.first_risk_by_threshold={k:None for k in ("0.10","0.15","0.30")}
        self.dd_hours={k:{"all":0,"with_regular":0,"without_regular":0,"s01_warning_during_held":0} for k in ("0.10","0.15","0.30")}
        self.max_drawdown=D(0);self.max_at=None;self.peak=None
        self.seen_eligible_entries=set();self.first_signal_per_entry=[]
        self.total_coincident_s01_signal_hours=0

    def _snapshot(self,at,positions,dust,cash,equity,hwm,dd,features):
        native={}
        for symbol,p in sorted(positions.items()):
            curr=features[symbol]
            native[symbol]={"quantity":str(dec(p.quantity)),"remaining_cost_basis":str(dec(p.cost_basis)),
                             "slots":p.slots,"allocation_units":p.allocation_units,
                             "native_entry_signal_id":p.signal.signal_id,
                             "last_completed_close":str(curr["last_completed_close"]),
                             "EMA72":str(curr["ema72"]),
                             "below_EMA72_completed_6h":curr["below_ema_6h"],
                             "estimated_liquidation_net_return_pct":str(curr["net_return_pct"]),
                             "S01_preregistered_warning":curr["s01_warning"]}
        return {"close_utc":at.isoformat(),"equity_usdc":str(equity),"cash_usdc":str(cash),
                "hwm_usdc":str(hwm),"hwm_dd_pct":str(dd*100),
                "native_regular_positions_count":len(positions),
                "native_regular_slot_count":sum(x.slots for x in positions.values()),
                "native_regular_positions":native,
                "dust_symbols_nonzero":[k for k,v in sorted(dust.items()) if dec(v)>0],
                "dust_balance_not_a_native_regular_position":True,
                "original_pending_orders":"NOT_VERIFIED",
                "no_trades_or_restrictions_placed_by_diagnostic":True}

    def on_closed(self,*,equity,hwm,cash,close_time,positions,dust,candles):
        equity=dec(equity);hwm=dec(hwm);cash=dec(cash)
        if equity<=0 or hwm<equity or hwm<=0:raise RuntimeError("BAD_NATIVE_EQUITY")
        dd=(hwm-equity)/hwm
        if self.total_hours and close_time-self.last_close!=timedelta(hours=1):
            raise RuntimeError("NONCONTIGUOUS_NATIVE_CLOSED_BARS")
        self.total_hours+=1;self.last_close=close_time
        if positions:self.sample_count_with_regular+=1
        elif any(dec(v)>0 for v in dust.values()):self.sample_count_with_only_dust+=1
        else:self.sample_count_with_no_balances+=1
        features={}
        for symbol,p in positions.items():
            if symbol not in self.f or close_time not in self.f[symbol]:
                raise RuntimeError("MISSING_COMPLETED_EMA_FEATURE:"+symbol)
            last,ema,persistence=self.f[symbol][close_time]
            held=dec(p.quantity);basis=dec(p.cost_basis)
            if held<=0 or basis<=0:raise RuntimeError("BAD_NATIVE_REMAINING_BASIS:"+symbol)
            net=held*last*(ONE-self.costs.adverse_price_rate)*(ONE-self.costs.fee_rate)
            profit_pct=(net/basis-ONE)*D(100)
            is_warning=persistence>=5 and profit_pct<=D("-4")
            features[symbol]={"last_completed_close":last,"ema72":ema,
                              "below_ema_6h":persistence,"net_return_pct":profit_pct,
                              "s01_warning":is_warning}
            if is_warning:
                marker=(symbol,p.signal.signal_id)
                if marker not in self.seen_eligible_entries:
                    self.seen_eligible_entries.add(marker)
                    if len(self.first_signal_per_entry)<100:
                        self.first_signal_per_entry.append({
                            "coin":symbol,"entry_signal_id":p.signal.signal_id,
                            "first_warning_close_utc":close_time.isoformat(),
                            "portfolio_dd_at_first_warning_pct":str(dd*100),
                            "net_unrealized_at_signal_pct":str(profit_pct),
                            "six_completed_below_ema":persistence,
                            "real_native_regular_position":True})
        any_warn=any(f["s01_warning"] for f in features.values())
        if any_warn:self.total_coincident_s01_signal_hours+=1
        snap=None
        for threshold in (D("0.10"),D("0.15"),D("0.30")):
            k=str(threshold)
            if dd>=threshold:
                b=self.dd_hours[k];b["all"]+=1
                b["with_regular" if positions else "without_regular"]+=1
                if any_warn:b["s01_warning_during_held"]+=1
                if self.first_risk_by_threshold[k] is None:
                    if snap is None:snap=self._snapshot(close_time,positions,dust,cash,equity,hwm,dd,features)
                    self.first_risk_by_threshold[k]=snap
        if dd>self.max_drawdown:
            self.max_drawdown=dd
            if snap is None:snap=self._snapshot(close_time,positions,dust,cash,equity,hwm,dd,features)
            self.max_at=snap
        if dd==0 and (self.peak is None or hwm>dec(self.peak["hwm_usdc"])):
            self.peak=self._snapshot(close_time,positions,dust,cash,equity,hwm,dd,features)
    def report(self):
        return {"case":self.window+"__"+self.cost,"status":"NATIVE_ACTIVE_POSITION_AND_CAUSAL_EMA_SIGNAL_OBSERVED",
                "native_frozen_control_equity_identity_required":True,
                "hours":self.total_hours,
                "hours_with_native_regular_positions":self.sample_count_with_regular,
                "hours_with_only_dust":self.sample_count_with_only_dust,
                "hours_with_no_native_coin_balance":self.sample_count_with_no_balances,
                "C0_total_S01_qualifying_closed_hours":self.total_coincident_s01_signal_hours,
                "C0_first_S01_warning_per_native_entry":self.first_signal_per_entry,
                "C0_count_distinct_entries_with_S01_warning":len(self.seen_eligible_entries),
                "first_closed_bar_portfolio_risk_warnings":self.first_risk_by_threshold,
                "closed_hour_risk_counts":self.dd_hours,
                "largest_C0_percentage_drawdown":self.max_at,
                "last_observed_C0_HWM_peak":self.peak,
                "causal_interpretation_limit":"No candidate protective fills, no cooldown simulation, no inference of improvement or independent OOS; future troughs used only to report observed historical exposure."}

def run(bundle,window,cost,out):
    bundle=pathlib.Path(bundle).resolve(strict=True)
    source_run=runpy.run_path(str(bundle/"run_baseline.py"),run_name="r2_s01_original_contract_verify")
    frozen_contract,manifest=source_run["verify"]()
    data,spec,contract,base,rules,CostModel=snapshot_loader(bundle=bundle,kind="historical",window=window)
    if contract!=frozen_contract:raise RuntimeError("CONTRACT_MUTATED")
    features=s01_features_from_closed_candles(data)
    model=CostModel(**{k:dec(v) if k!="name" else v for k,v in contract["costs"][cost].items()})
    observer=PositionObserver(features,model,window,cost)
    orig=(bundle/"engine/src/hixton/backtest/portfolio.py").read_text(encoding="utf-8")
    if hashlib.sha256(orig.encode()).hexdigest()!=FROZEN_NATIVE_PORTFOLIO_SHA:
        raise RuntimeError("FROZEN_NATIVE_SOURCE_HASH_CHANGED")
    needle="            new_pending: list[Signal] = []\n"
    if orig.count(needle)!=1:raise RuntimeError("NATIVE_PROBE_INJECTION_NONUNIQUE")
    patch="""            R2_S01_OBSERVER.on_closed(
                equity=equity, hwm=closed_high_water, cash=cash,
                close_time=max(candle.close_time_utc for candle in row),
                positions=positions, dust=dust, candles=candles)
"""
    isolated=orig.replace(needle,patch+needle)
    mod=types.ModuleType("hixton.backtest.r2_s01_observer_isolated")
    mod.__file__=str(pathlib.Path(__file__).resolve());mod.__package__="hixton.backtest"
    mod.R2_S01_OBSERVER=observer
    sys.modules[mod.__name__]=mod
    exec(compile(isolated,mod.__file__,"exec"),mod.__dict__)
    seed=dec(spec["seed"])
    result=mod.run_shared_portfolio_backtest(
        candles_by_symbol=data,
        report_start_utc=datetime.fromisoformat(spec["start"]),
        report_end_utc=datetime.fromisoformat(spec["end"]),
        starting_cash=seed,
        target_notional=(seed/2).quantize(D(".01"),rounding=ROUND_DOWN),
        slot_count=2,costs=model,execution_rules=rules,strategy=base,
        reinvest_profits=True,profit_reinvestment_fraction=ONE,
        capital_exposure_fraction=ONE,autonomous_spot=True)
    baseline_path=bundle/spec["baseline"][cost]["path"]
    reference=json.loads((baseline_path/"Result.json").read_text())
    assert_native(result,reference,window=window,cost=cost,bundle=bundle,spath=baseline_path,control=True)
    doc=observer.report()
    doc.update({"status":"NATIVE_CONTROL_PARITY_AND_OBSERVED_POSITION_CAUSAL_FEATURES_PASS",
                "C0_start_usdc":str(seed),"C0_end_usdc":str(result.metrics.ending_equity),
                "original_frozen_native_portfolio_sha256":FROZEN_NATIVE_PORTFOLIO_SHA,
                "original_input_contract_sha256":digest(bundle/"Input-Contract.json"),
                "original_candle_snapshot_sha256_by_symbol":result.data_snapshot_sha256_by_symbol,
                "research_overlay_sha256":hashlib.sha256(isolated.encode()).hexdigest(),
                "source_version":"f56d48536525830dd6ea50bf5bc174a6f9aeff8c",
                "no_extra_orders":True,"zero_candidate_financial_simulations":True})
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(out).write_text(json.dumps(doc,indent=2,default=str)+"\n")
    print("R2_S01_NATIVE_POSITION_DIAGNOSTIC",json.dumps({"status":doc["status"],"case":doc["case"],
      "hours":doc["hours"],"hours_with_real_regular_position":doc["hours_with_native_regular_positions"],
      "hours_only_dust":doc["hours_with_only_dust"],
      "entries_with_preexisting_s01_warning":doc["C0_count_distinct_entries_with_S01_warning"],
      "largest_dd_native_regular_positions":(doc["largest_C0_percentage_drawdown"] or {}).get("native_regular_positions_count")}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",required=True)
    p.add_argument("--window",default="original_32k",choices=("original_32k","current_26oct","latest_long"))
    p.add_argument("--cost",default="current",choices=("current","stress"))
    p.add_argument("--output",required=True)
    a=p.parse_args();run(a.bundle,a.window,a.cost,a.output)

"""Research-only compound-capital V8 backtest: 1100 USDC start, NOT a fixed lifetime cap.

Every future entry uses current marked-to-market managed portfolio equity.
Never reads API secrets, submits orders, or changes canonical hixton modules.
A private, in-memory copy of the tested portfolio model makes the one-line
sizing injection explicit and reproducible; no live/paper module is patched.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, tempfile
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path
from hixton.backtest.continuity import load_continuity_history, continuity_manifest_data
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.storage import CandleStore
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.versions import strategy_definition
from hixton.domain.strategy import entry_priority
from hixton.backtest import portfolio as original
from research_capital1100_paper_20261011 import _metrics, _leverage_liquidation_sensitivity

STARTING = D("1100")
SIZING_SOURCE = "                budget = min(target_notional * Decimal(allocated_slots), cash)"
# Mark EVERY bot-owned position and dust at NEXT execution candle opening prices.
SIZING_REPLACEMENT = """                research_marked_equity = (
                    cash + sum(
                        positions[s].quantity * _d(candles[s].open)
                        for s in positions
                    ) + sum(
                        qty * _d(candles[s].open)
                        for s, qty in dust.items()
                    )
                )
                # target_notional / starting_cash is a fixed FRACTION,
                # but its USDC value grows/shrinks with available equity.
                research_budget_per_slot = max(
                    ZERO, research_marked_equity * target_notional / starting_cash
                )
                budget = min(research_budget_per_slot * Decimal(allocated_slots), cash)"""
# Slots are capacity gates and per-coin limits. No forced investment when signals
# are missing, and no borrowing or leverage is created.

CASES = (
 ("compound_2x550", 2, D("550"), RANKED_REPEAT, False),
 ("compound_3x366_66", 3, D("366.66"), RANKED_REPEAT, False),
 ("compound_4x250_buffer100", 4, D("250"), RANKED_REPEAT, False),
 ("compound_4x275", 4, D("275"), RANKED_REPEAT, False),
 ("compound_5x220", 5, D("220"), RANKED_REPEAT, False),
 ("compound_4x250_one_per_symbol", 4, D("250"), ONE_PER_SYMBOL, False),
 ("compound_dynamic_4x250", 4, D("250"), RANKED_REPEAT, True),
 ("compound_dynamic_4x275", 4, D("275"), RANKED_REPEAT, True),
)


def load_patched_module():
    source = Path(original.__file__).read_text()
    if source.count(SIZING_SOURCE) != 1:
        raise RuntimeError("Canonical sizing point has drifted; refuse experiment")
    candidate = source.replace(SIZING_SOURCE, SIZING_REPLACEMENT)
    # Sanity check: no other instruction in the canonical engine changed.
    assert candidate.replace(SIZING_REPLACEMENT, SIZING_SOURCE) == source
    name = "hixton.backtest._research_compound_only"
    with tempfile.TemporaryDirectory() as td:
        file = Path(td) / "compound_only.py"
        file.write_text(candidate)
        spec = importlib.util.spec_from_file_location(name, file)
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot load isolated research copy")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module, hashlib.sha256(source.encode()).hexdigest(), hashlib.sha256(candidate.encode()).hexdigest()


def run(mod,*,strategy,candles,rules,start,end,cost,name,slots,tranche,policy,adaptive):
    original_allocation=mod.allocate_entry_slots
    original_rank=mod.entry_priority
    strengths={}
    def capture(strength,symbol,symbols):
        strengths[symbol] = max(0.0,float(strength or 0.0))
        return original_rank(strength,symbol,symbols)
    def adaptive_slots(symbols,*,free_slots,policy):
        if policy != RANKED_REPEAT:
            return original_allocation(symbols,free_slots=free_slots,policy=policy)
        unique=tuple(dict.fromkeys(symbols))
        chosen=unique[:free_slots]
        assigned=dict.fromkeys(chosen,1)
        remaining=free_slots-len(chosen)
        for symbol in chosen:
            score=strengths.get(symbol,0.0)
            limit = 3 if score>=1.0 else 2 if score>=0.25 else 1
            units=min(remaining,limit-1)
            assigned[symbol]+=units
            remaining-=units
            if remaining<=0:break
        return assigned
    try:
        if adaptive:
            mod.entry_priority=capture
            mod.allocate_entry_slots=adaptive_slots
        from dataclasses import replace
        candidate=replace(strategy,slot_allocation=policy)
        return mod.run_shared_portfolio_backtest(
            candles_by_symbol=candles,
            report_start_utc=start,report_end_utc=end,
            starting_cash=STARTING,
            target_notional=tranche,
            slot_count=slots,
            costs=cost,
            execution_rules=rules,
            strategy=candidate,
        )
    finally:
        mod.allocate_entry_slots=original_allocation
        mod.entry_priority=original_rank


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--end",required=True)
    p.add_argument("--database",default="data/hixton-usdc.sqlite3")
    p.add_argument("--output",default="evidence/hixton-capital1100-compounding.json")
    args=p.parse_args()
    end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(UTC)
    start=end.replace(year=end.year-3)
    if any((end.minute,end.second,end.microsecond)):
        raise ValueError("Only closed full UTC hour")
    mod,canonical_sha,compound_sha=load_patched_module()
    strategy=strategy_definition("v8")
    if len(strategy.symbols)!=15:
        raise ValueError("Unexpected market universe")
    db=Path(args.database)
    rules={}
    with CandleStore(db,read_only=True) as store:
        for symbol in strategy.symbols:
            item=store.load_symbol_rules(symbol)
            if item is None or item.status!="TRADING" or not item.spot_allowed:
                raise ValueError("Missing public Binance Spot execution rule "+symbol)
            rules[symbol]=ExecutionRules(
                item.tick_size,item.step_size,item.min_qty,item.min_notional)
    history=load_continuity_history(
        strategy=strategy,
        report_start_utc=start,report_end_utc=end,
        execution_rules=rules,
        native_database_path=db,
        cache_path=db.parent/"backtest-history.sqlite3",
        client=BinancePublicClient(base_url="https://data-api.binance.vision"))
    result={}
    leverage_screen=None
    fixed_reference={}
    for cost in (CURRENT_COSTS,STRESS_COSTS):
        run_fixed=original.run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=start,report_end_utc=end,
            starting_cash=STARTING,target_notional=D("550"),slot_count=2,
            costs=cost,execution_rules=rules,strategy=strategy)
        fixed_reference[cost.name]=_metrics(run_fixed,start,end)
        print("REFERENCE_FIXED_2x550",cost.name,
              fixed_reference[cost.name]["end_usdc"],flush=True)
    for label,slots,tranche,policy,adaptive in CASES:
        if slots*tranche>STARTING:
            raise ValueError("Gross collateral commitment exceeds portfolio start")
        row={"slots":slots,"start_per_slot_usdc":str(tranche),
             "initial_reserve_usdc":str(STARTING-slots*tranche),
             "adaptive_signal_sizing":adaptive,
             "costs":{}}
        for cost in (CURRENT_COSTS,STRESS_COSTS):
            run_result=run(
                mod,strategy=strategy,candles=history.candles_by_symbol,
                rules=rules,start=start,end=end,cost=cost,name=label,
                slots=slots,tranche=tranche,policy=policy,adaptive=adaptive)
            row["costs"][cost.name]=_metrics(run_result,start,end)
            print("COMPOUND",label,cost.name,
                  row["costs"][cost.name]["end_usdc"],
                  "completed",run_result.metrics.completed_trades,
                  "drawdown",run_result.metrics.max_drawdown_pct,flush=True)
            if label=="compound_4x250_buffer100" and cost.name=="current":
                leverage_screen=_leverage_liquidation_sensitivity(
                    run_result,history.candles_by_symbol,cost)
        result[label]=row
    for row in result.values():
        row["versus_fixed_canonical"]={}
        for cost in ("current","stress"):
            row["versus_fixed_canonical"][cost]={
                "delta_equity_usdc":str(
                    D(row["costs"][cost]["end_usdc"])-
                    D(fixed_reference[cost]["end_usdc"])),
                "delta_trades":row["costs"][cost]["trades"]-
                    fixed_reference[cost]["trades"],
            }
    proof={
      "starting_balance_usdc":str(STARTING),
      "quote_currency":"USDC",
      "period":{"start":start.isoformat(),"end":end.isoformat()},
      "capital_rule":"Fractional slots sized at each NEXT execution candle OPEN from cash + bot-owned marked positions + dust; downsize after losses and upsize after gains. Positions not forcibly rebalanced; unused cash is allowed. No borrowing.",
      "externally_added_or_withdrawn_funds_simulated":False,
      "auth_binance_account_read":False,
      "canonical_source_sha256":canonical_sha,
      "isolated_research_variant_sha256":compound_sha,
      "baseline_unchanged":True,
      "order_execution":"NONE",
      "fixed_budget_comparison":fixed_reference,
      "compound_scenarios":result,
      "leverage_risk_screen_only":leverage_screen,
      "data_provenance":continuity_manifest_data(history),
      "conclusion_gate":"RESEARCH_ONLY_NOT_OOS_NOT_DERIVATIVES_AND_NOT_LIVE_APPROVED",
    }
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(proof,indent=2,ensure_ascii=False)+"\n")
    print("SAVED",output,flush=True)


if __name__=="__main__":
    main()

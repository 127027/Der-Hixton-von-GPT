"""R2-D3-S01 research-only native runner: exact original f56 loader and ledger.

Never imports live trading; requires verified historical/synthetic original packages.
--mode control checks full original C0 identity; candidate measures S01 outcomes.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,runpy,sys,types
from datetime import datetime
from decimal import Decimal as D, ROUND_DOWN

from research.r2_hold003.run_native import (
    FROZEN,FROZEN_SOURCE,FROZEN_NATIVE_PORTFOLIO_SHA,
    snapshot_loader,assert_native,episodes,quarters,digest,primitive,write
)
from research.r2_s01.native_frozen_c0_position_observer import s01_features_from_closed_candles

HIST=("original_32k","current_26oct","latest_long")
SYNTH=("cycles","winter","whipsaw","rotation","tail")
COSTS=("current","stress")

def run(args):
    bundle=pathlib.Path(args.bundle).resolve(strict=True)
    output=pathlib.Path(args.output).resolve()
    if output.exists():raise RuntimeError("S01_NO_RESULT_OVERWRITE")
    kind="historical" if args.window in HIST else "synthetic"
    wrapper="run_baseline.py" if kind=="historical" else "run_synthetic_baseline.py"
    # Original wrapped verifier also validates the original payload hashes.
    verified=runpy.run_path(str(bundle/wrapper),run_name="s01_original_verification")
    frozen_contract,_=verified["verify"]()
    data,spec,contract,base,rules,CostModel=snapshot_loader(bundle=bundle,kind=kind,window=args.window)
    from research.r2_s01.native_s01_policy import S01Policy,instrument
    if contract != frozen_contract:raise RuntimeError("S01_CONTRACT_VERIFICATION_MISMATCH")
    if contract["source_commit"]!=FROZEN or contract["source_sha256_normalized"]!=FROZEN_SOURCE:
        raise RuntimeError("S01_ORIGINAL_PRODUCT_DRIFT")
    costs=CostModel(**{k:D(v) if k!="name" else v for k,v in contract["costs"][args.cost].items()})
    # Prevent importing a hypothetical/future label into S01: original chronological candles only.
    features=s01_features_from_closed_candles(data)
    orig=(bundle/"engine/src/hixton/backtest/portfolio.py").read_text(encoding="utf-8")
    if hashlib.sha256(orig.encode()).hexdigest()!=FROZEN_NATIVE_PORTFOLIO_SHA:
        raise RuntimeError("S01_FROZEN_NATIVE_PORTFOLIO_HASH_MISMATCH")
    isolated=instrument(orig)
    policy=S01Policy(features=features,costs=costs,enabled=args.mode=="candidate")
    mod=types.ModuleType("hixton.backtest.r2_s01_isolated")
    mod.__file__=str(pathlib.Path(__file__).resolve())
    mod.__package__="hixton.backtest"
    mod.R2_S01=policy
    sys.modules[mod.__name__]=mod
    exec(compile(isolated,mod.__file__,"exec"),mod.__dict__)
    seed=D(spec["seed"])
    result=mod.run_shared_portfolio_backtest(
        candles_by_symbol=data,report_start_utc=datetime.fromisoformat(spec["start"]),
        report_end_utc=datetime.fromisoformat(spec["end"]),starting_cash=seed,
        target_notional=(seed/2).quantize(D(".01"),rounding=ROUND_DOWN),
        slot_count=2,costs=costs,execution_rules=rules,strategy=base,
        reinvest_profits=True,profit_reinvestment_fraction=D(1),
        capital_exposure_fraction=D(1),autonomous_spot=True)
    baseline_path=bundle/spec["baseline"][args.cost]["path"]
    reference=json.loads((baseline_path/"Result.json").read_text())
    assert_native(result,reference,window=args.window,cost=args.cost,bundle=bundle,
                  spath=baseline_path,control=args.mode=="control")
    from research.r2_s01.native_ledger_independent_audit import audit_s01_native_result
    ledger_audit = audit_s01_native_result(result=result, policy=policy, costs=costs)
    absdd,pctdd=episodes(result)
    record=dict(
        id="R2-D3-S01",research_only=True,product_unchanged=True,
        mode=args.mode,window=args.window,cost=args.cost,
        status="C0_EXACT_PARITY" if args.mode=="control" else "CANDIDATE_DEVELOPMENT_ONLY",
        native_source_sha256=FROZEN_NATIVE_PORTFOLIO_SHA,
        frozen_product=FROZEN,source_sha256=FROZEN_SOURCE,
        original_input_contract_sha256=digest(bundle/"Input-Contract.json"),
        overlay_source_sha256=hashlib.sha256(isolated.encode()).hexdigest(),
        snapshot_sha256_by_symbol=result.data_snapshot_sha256_by_symbol,
        starting_equity_usdc=seed,
        C0_ending_equity_usdc=reference["metrics"]["ending_equity"],
        candidate_ending_equity_usdc=result.metrics.ending_equity,
        candidate_max_drawdown_pct=result.metrics.max_drawdown_pct,
        ending_equity_delta_usdc=result.metrics.ending_equity-D(str(reference["metrics"]["ending_equity"])),
        native_metrics=result.metrics,
        native_fill_count=len(result.fills),native_trade_count=len(result.trades),
        native_total_fees=sum((x.fee_quote_equivalent for x in result.fills),D(0)),
        native_total_spread_slippage=sum((x.modeled_spread_slippage for x in result.fills),D(0)),
        absolute_drawdown_episode=absdd,percentage_drawdown_episode=pctdd,
        synthetic_20_quarters=quarters(result,spec),
        s01_events=policy.events,
        native_s01_fill_trade_ledger_audit=ledger_audit,
        s01_executed_count=sum(x["kind"]=="FILLED_NATIVE_FULL_EXIT" for x in policy.events),
        native_execution_semantics="UNCHANGED_F56_EXECUTE_EXIT_CLOSURE",
        partial_live_fill_semantics="NOT_MODELED_IN_FROZEN_NATIVE_BACKTEST",
    )
    write(output,record)
    print("R2_S01_NATIVE_RESULT",json.dumps({
        "status":record["status"],"window":args.window,"cost":args.cost,
        "mode":args.mode,"end":str(result.metrics.ending_equity),
        "exits":record["s01_executed_count"]}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",required=True)
    p.add_argument("--window",required=True,choices=HIST+SYNTH)
    p.add_argument("--cost",required=True,choices=COSTS)
    p.add_argument("--mode",required=True,choices=("control","candidate"))
    p.add_argument("--output",required=True)
    run(p.parse_args())

"""Key-free, research-only V8 15-market portfolio ablation; no orders or production changes."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path
from hixton.backtest.continuity import load_continuity_history, continuity_manifest_data
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.binance import BinancePublicClient
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

CAPITAL = D("250")
FILLERS = ("NEARUSDC", "AAVEUSDC", "BCHUSDC")
CASES = (
    ("baseline", FILLERS, 2),
    ("core_only", (), 2),
    ("near_only", ("NEARUSDC",), 2),
    ("aave_only", ("AAVEUSDC",), 2),
    ("bch_only", ("BCHUSDC",), 2),
    ("near_aave", ("NEARUSDC", "AAVEUSDC"), 2),
    ("near_bch", ("NEARUSDC", "BCHUSDC"), 2),
    ("aave_bch", ("AAVEUSDC", "BCHUSDC"), 2),
    ("baseline_plus_sui", FILLERS + ("SUIUSDC",), 2),
    ("baseline_plus_uni", FILLERS + ("UNIUSDC",), 2),
    ("all_five", FILLERS + ("SUIUSDC", "UNIUSDC"), 2),
    ("one_slot", FILLERS, 1),
    ("three_slots", FILLERS, 3),
)

def summary(run, start, end):
    m = run.metrics
    yearly = []
    previous = CAPITAL
    for offset in (1, 2, 3):
        boundary = start.replace(year=start.year + offset)
        value = m.ending_equity if boundary == end else next(
            (p.equity for p in reversed(run.equity_curve) if p.time_utc < boundary), previous)
        yearly.append({"year": offset, "end_usdc": str(value), "pnl_usdc": str(value-previous)})
        previous = value
    coins = defaultdict(lambda: {"trades":0, "wins":0, "pnl":D(0)})
    for trade in run.trades:
        coins[trade.symbol]["trades"] += 1
        coins[trade.symbol]["wins"] += int(trade.realized_pnl > 0)
        coins[trade.symbol]["pnl"] += trade.realized_pnl
    return {
        "ending_equity":str(m.ending_equity), "net_pnl":str(m.net_pnl),
        "trades":m.completed_trades, "slot_trades":m.completed_slot_trades,
        "winning_trades":m.winning_trades, "win_rate_pct":str(m.win_rate_pct),
        "profit_factor":str(m.profit_factor), "drawdown_pct":str(m.max_drawdown_pct),
        "drawdown_usdc":str(m.max_drawdown), "exposure_pct":str(m.exposure_pct),
        "fees_usdc":str(m.total_fees),
        "spread_slippage_usdc":str(m.modeled_spread_slippage),
        "yearly":yearly,
        "per_coin":{s:{"trades":v["trades"],"wins":v["wins"],"realized_pnl":str(v["pnl"])}
                    for s,v in coins.items()},
        "blocked_reasons":dict(Counter(x.rsplit(":",1)[-1] for x in run.blocked_signals)),
        "active_bars":sum(bool(p.active_position) for p in run.equity_curve),
        "bars":len(run.equity_curve), "open_symbols_end":list(run.open_symbols_at_end),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--end",required=True)
    ap.add_argument("--database",default="data/hixton-usdc.sqlite3")
    ap.add_argument("--output",default="evidence/research-v8-ablation-20261011.json")
    args=ap.parse_args()
    end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(UTC)
    start=end.replace(year=end.year-3)
    strategy=strategy_definition("v8")
    if end.minute or end.second or end.microsecond:
        raise ValueError("Backtest end must be a closed UTC hour")
    if strategy.active_shared_satellites != FILLERS or len(strategy.symbols)!=15:
        raise ValueError("Canonical V8 strategy contract changed; stop instead of inventing comparison")
    db=Path(args.database)
    rules={}
    with CandleStore(db,read_only=True) as store:
        for symbol in strategy.symbols:
            r=store.load_symbol_rules(symbol)
            if not r or r.status!="TRADING" or not r.spot_allowed or "MARKET" not in r.order_types:
                raise ValueError(f"{symbol}: missing live-compatible public USDC rules")
            rules[symbol]=ExecutionRules(r.tick_size,r.step_size,r.min_qty,r.min_notional)
    history=load_continuity_history(
        strategy=strategy,report_start_utc=start,report_end_utc=end,
        execution_rules=rules,
        client=BinancePublicClient(base_url="https://data-api.binance.vision"),
        native_database_path=db,cache_path=db.parent/"backtest-history.sqlite3")
    results={}
    for label,active,slots in CASES:
        print("RUN",label,"fillers",active,"slots",slots,flush=True)
        candidate=replace(strategy,active_shared_satellites=active)
        scenarios={}
        for cost in (CURRENT_COSTS,STRESS_COSTS):
            run=run_shared_portfolio_backtest(
                candles_by_symbol=history.candles_by_symbol,execution_rules=rules,
                starting_cash=CAPITAL,target_notional=CAPITAL/D(slots),
                slot_count=slots,strategy=candidate,
                report_start_utc=start,report_end_utc=end,costs=cost)
            scenarios[cost.name]=summary(run,start,end)
            print(" ",cost.name,"equity",scenarios[cost.name]["ending_equity"],
                  "trades",run.metrics.completed_trades,flush=True)
        results[label]={"active_fillers":list(active),"slots":slots,"scenarios":scenarios}
    baseline=results["baseline"]["scenarios"]["current"]
    matching=(baseline["trades"]==198 and abs(D(baseline["ending_equity"])-D("1601.35"))<=D("0.10"))
    for key,row in results.items():
        row["versus_baseline"]={}
        for cost in ("current","stress"):
            candidate=row["scenarios"][cost]
            base=results["baseline"]["scenarios"][cost]
            row["versus_baseline"][cost]={
                "delta_end_usdc":str(D(candidate["ending_equity"])-D(base["ending_equity"])),
                "delta_trades":candidate["trades"]-base["trades"],
                "delta_drawdown_pp":str(D(candidate["drawdown_pct"])-D(base["drawdown_pct"])),
                "delta_year3_pnl_usdc":str(D(candidate["yearly"][2]["pnl_usdc"])-D(base["yearly"][2]["pnl_usdc"])),
            }
    payload={
        "source_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "strategy_version":strategy.version,"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "start_utc":start.isoformat(),"end_utc":end.isoformat(),
        "capital_usdc":"250","canonical_baseline_matches_prior_run":matching,
        "history":continuity_manifest_data(history),
        "cost_models":{"current":"10 fee + 2 spread + 3 slippage bps / side",
                       "stress":"10 fee + 10 spread + 20 slippage bps / side"},
        "scenarios":results,"status":"RESEARCH_ONLY_NOT_OOS_OR_RELEASE_APPROVED",
        "orders_sent":False,"V6_and_product_modified":False}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n")
    print("EVIDENCE",out,"base_reproduced",matching,flush=True)
    if not matching:
        raise RuntimeError("Historical baseline mismatch; candidate promotion blocked")

if __name__=="__main__":
    main()

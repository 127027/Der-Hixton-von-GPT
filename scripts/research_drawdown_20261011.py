"""Reproducible isolated drawdown research; no credentials or order endpoints."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

CANDIDATES = {
    "baseline": (0, 0),
    "stop_2": (2, 0),
    "stop_3": (3, 0),
    "trail_6": (0, 6),
    "stop_3_trail_6": (3, 6),
    "stop_3_trail_10": (3, 10),
    "stop_4_trail_10": (4, 10),
}
ENTRY_CANDIDATES = {
    "baseline": (0, 0),
    "slope24": (0, 0),
    "cmo20": (0, 0),
    "slope24_cmo20": (0, 0),
    "cmo40": (0, 0),
    "slope24_cmo40": (0, 0),
    "one_per_coin": (0, 0),
    "core_only": (0, 0),
}
CAPITAL_CANDIDATES = {
    "baseline": (0, 0),
    "profits50": (0, 0),
    "profits25": (0, 0),
    "core_profits50": (0, 0),
    "core_profits25": (0, 0),
}
EXPOSURE_CANDIDATES = {
    "baseline": (0, 0),
    "exposure75": (0, 0),
    "exposure50": (0, 0),
    "exposure35": (0, 0),
}


def candidate(name):
    base = strategy_definition("v8")
    stop, trail = CANDIDATES[name]
    if name == "baseline":
        return base
    profiles = tuple(
        replace(
            p,
            trade_policy=replace(
                p.trade_policy,
                stop_atr=min(p.trade_policy.stop_atr, stop)
                if stop and p.trade_policy.stop_atr
                else stop or p.trade_policy.stop_atr,
                trail_atr=trail or p.trade_policy.trail_atr,
                slope_bars=max(p.trade_policy.slope_bars, 24 if "slope24" in name else 0),
                cmo_floor=max(
                    p.trade_policy.cmo_floor,
                    0.4 if "cmo40" in name else 0.2 if "cmo20" in name else 0,
                ),
            ),
        )
        if p.symbol not in base.satellite_symbols
        else p
        for p in base.coin_profiles
    )
    return replace(
        base,
        coin_profiles=profiles,
        version="HIXTON-V8-RESEARCH-DD-" + name,
        paper_approved=False,
        slot_allocation="one_per_symbol" if name == "one_per_coin" else base.slot_allocation,
        active_shared_satellites=() if name.startswith("core_") else base.active_shared_satellites,
    )


def stats(run):
    m = run.metrics
    peak = run.starting_cash
    peak_time = run.report_start_utc
    worst = D(0)
    interval = None
    for p in run.equity_curve:
        if p.equity > peak:
            peak = p.equity
            peak_time = p.time_utc
        dd = (1 - p.equity / peak) * 100
        if dd > worst:
            worst = dd
            interval = {
                "peak": str(peak),
                "trough": str(p.equity),
                "peak_time": peak_time.isoformat(),
                "trough_time": p.time_utc.isoformat(),
            }
    coins = defaultdict(lambda: {"trades": 0, "losses": 0, "pnl": D(0), "worst_return_pct": D(0)})
    for t in run.trades:
        c = coins[t.symbol]
        c["trades"] += 1
        c["losses"] += t.realized_pnl < 0
        c["pnl"] += t.realized_pnl
        c["worst_return_pct"] = min(c["worst_return_pct"], t.realized_return_pct)
    return {
        "end_usdc": str(m.ending_equity),
        "return_pct": str(m.return_pct),
        "dd_pct": str(m.max_drawdown_pct),
        "trades": m.completed_trades,
        "fees_usdc": str(m.total_fees),
        "modeled_slippage_usdc": str(m.modeled_spread_slippage),
        "drawdown_interval": interval,
        "coin_attribution": dict(coins),
        "open_symbols": run.open_symbols_at_end,
    }


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--data", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--family", choices=("exits", "entries", "capital", "exposure"), default="exits")
    args = a.parse_args()
    data = Path(args.data)
    out = Path(args.out)
    if args.family == "entries":
        CANDIDATES.clear()
        CANDIDATES.update(ENTRY_CANDIDATES)
    if args.family == "capital":
        CANDIDATES.clear()
        CANDIDATES.update(CAPITAL_CANDIDATES)
    if args.family == "exposure":
        CANDIDATES.clear()
        CANDIDATES.update(EXPOSURE_CANDIDATES)
    start = datetime(2023, 10, 11, 15, tzinfo=UTC)
    end = datetime(2026, 10, 11, 15, tzinfo=UTC)
    seed = D("1092.05773944")
    base = strategy_definition("v8")
    rules = {}
    with CandleStore(data / "hixton-usdc.sqlite3", read_only=True) as store:
        for sym in base.symbols:
            r = store.load_symbol_rules(sym)
            rules[sym] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
    history = load_continuity_history(
        strategy=base,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
        native_database_path=data / "hixton-usdc.sqlite3",
        cache_path=data / "backtest-history.sqlite3",
    )
    rows = {}
    results = {
        "period": [start.isoformat(), end.isoformat()],
        "seed": str(seed),
        "data": continuity_manifest_data(history),
        "kind": "PREVIOUSLY_EXAMINED_HISTORY_TEMPORAL_REJECTION_NOT_UNSEEN_OUT_OF_SAMPLE",
        "selection_rule": (
            "Both training folds: positive return, at least 60% baseline profit, "
            "DD lower by at least 20% relative; rank by worst-fold return/DD. "
            "Validation rejection only."
        ),
        "train": rows,
    }

    def run(name, label, s, e, costs, compound=True):
        t = time.monotonic()
        r = run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=s,
            report_end_utc=e,
            starting_cash=seed,
            target_notional=seed / 2,
            slot_count=2,
            execution_rules=rules,
            strategy=candidate(name),
            costs=costs,
            reinvest_profits=compound,
            autonomous_spot=True,
            profit_reinvestment_fraction=D(".5")
            if "profits50" in name
            else D(".25")
            if "profits25" in name
            else D("1"),
            capital_exposure_fraction=D(".75")
            if "exposure75" in name
            else D(".50")
            if "exposure50" in name
            else D(".35")
            if "exposure35" in name
            else D("1"),
        )
        row = stats(r)
        print(
            name,
            label,
            costs.name,
            "end",
            row["end_usdc"],
            "DD",
            row["dd_pct"],
            "seconds",
            round(time.monotonic() - t, 1),
            flush=True,
        )
        return row

    def save():
        out.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")

    folds = [
        (start, start.replace(year=2024)),
        (start.replace(year=2024), start.replace(year=2025)),
    ]
    for name in CANDIDATES:
        rows[name] = [
            run(name, "train" + str(i), s, e, STRESS_COSTS) for i, (s, e) in enumerate(folds)
        ]
        save()
    if args.family == "exposure":
        results["selection_rule"] = (
            "Risk-priority experiment after rejection of entry/exit/profit overlays. "
            "Both training folds profitable, retain >=20% baseline profit, DD <=80% baseline; "
            "choose lowest worst training DD. Final year rejection only: lower DD and "
            "return >= min(0,baseline return). Reduced market exposure explicitly changes "
            "prior all-capital preference."
        )
    feasible = []
    for name, row in rows.items():
        if name == "baseline":
            continue
        passed = all(
            (
                D(r["return_pct"]) > 0
                and D(r["return_pct"])
                >= D(b["return_pct"]) * (D(".20") if args.family == "exposure" else D(".60"))
                and (D(r["dd_pct"]) <= D(b["dd_pct"]) * D(".80"))
                for r, b in zip(row, rows["baseline"], strict=True)
            )
        )
        if passed:
            feasible.append(name)
    results["training_accepted"] = feasible
    if not feasible:
        results["winner"] = None
        results["full"] = {
            "baseline": {
                c.name: run("baseline", "full", start, end, c)
                for c in (CURRENT_COSTS, STRESS_COSTS)
            }
        }
        save()
        print("NO_CANDIDATE_PASSED", flush=True)
        return
    winner = (
        min(feasible, key=lambda n: max(D(r["dd_pct"]) for r in rows[n]))
        if args.family == "exposure"
        else max(
            feasible,
            key=lambda n: min(D(r["return_pct"]) / max(D(r["dd_pct"]), D(".01")) for r in rows[n]),
        )
    )
    results["winner"] = winner
    results["validation"] = {}
    results["full"] = {}
    save()
    for name in ("baseline", winner):
        results["validation"][name] = {
            c.name: run(name, "validation", start.replace(year=2025), end, c)
            for c in (CURRENT_COSTS, STRESS_COSTS)
        }
        save()
        results["full"][name] = {
            c.name: run(name, "full", start, end, c) for c in (CURRENT_COSTS, STRESS_COSTS)
        }
        save()
    if args.family == "exposure":
        results["validation_passed"] = all(
            D(results["validation"][winner][c]["return_pct"])
            >= min(D(0), D(results["validation"]["baseline"][c]["return_pct"]))
            and D(results["validation"][winner][c]["dd_pct"])
            <= D(results["validation"]["baseline"][c]["dd_pct"]) * D(".80")
            for c in ("current", "stress")
        )
    else:
        results["validation_passed"] = all(
            D(results["validation"][winner][c]["return_pct"]) > 0
            and D(results["validation"][winner][c]["return_pct"])
            >= D(results["validation"]["baseline"][c]["return_pct"]) * D(".60")
            and (
                D(results["validation"][winner][c]["dd_pct"])
                <= D(results["validation"]["baseline"][c]["dd_pct"]) * D(".80")
            )
            for c in ("current", "stress")
        )
    results["full"]["baseline_fixed"] = run(
        "baseline", "full_fixed", start, end, CURRENT_COSTS, False
    )
    save()
    print("DONE", winner, "validation", results["validation_passed"], flush=True)


if __name__ == "__main__":
    main()

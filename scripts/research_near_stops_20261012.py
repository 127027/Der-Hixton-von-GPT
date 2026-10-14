"""Frozen NEAR stop family on a market-only snapshot; no runtime or private API."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

from research_coin_policies_20261011 import END, SEED, START, SnapshotOnly, summary

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import V8_VOLATILITY_INITIAL_PAPER_STRATEGY, strategy_definition

CATALOGUE = {"baseline": None, "stop2": 2.0, "stop3": 3.0, "stop4": 4.0, "stop6": 6.0}


def definition(name):
    base = V8_VOLATILITY_INITIAL_PAPER_STRATEGY
    if name == "original_v8":
        return strategy_definition("v8")
    if name == "baseline":
        return base
    threshold = CATALOGUE[name]
    return replace(
        base,
        paper_approved=False,
        version="HIXTON-V8-NEARSTOP-RESEARCH-" + name,
        coin_profiles=tuple(
            replace(p, trade_policy=replace(p.trade_policy, stop_atr=threshold))
            if p.symbol == "NEARUSDC"
            else p
            for p in base.coin_profiles
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    base = definition("baseline")
    rules = {}
    with CandleStore(args.data / "hixton-usdc.sqlite3", read_only=True) as store:
        for symbol in base.symbols:
            r = store.load_symbol_rules(symbol)
            rules[symbol] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
    history = load_continuity_history(
        strategy=base,
        report_start_utc=START,
        report_end_utc=END,
        execution_rules=rules,
        native_database_path=args.data / "hixton-usdc.sqlite3",
        cache_path=args.data / "backtest-history.sqlite3",
        client=SnapshotOnly(),
    )
    payload = {
        "status": "RESEARCH_ONLY",
        "installed": False,
        "orders_sent": False,
        "source_sha256": source_fingerprint(),
        "catalogue": CATALOGUE,
        "period": [START.isoformat(), END.isoformat()],
        "seed": str(SEED),
        "data": continuity_manifest_data(history),
        "train": {},
        "full": {},
        "last_year": {},
        "selection": (
            "Predeclared stop family 2/3/4/6 ATR on NEAR only. Two fresh-account stress-cost "
            "training years must remain profitable, retain >=95% V8r return and not raise "
            "DD. Rank worst-fold return/DD; freeze selection before last-year/full runs. "
            "Full both costs must retain >=95% V8r return and have DD <=80% original V8 DD. "
            "Last year both costs must not worsen V8r return or DD. Previously examined "
            "history; no pristine holdout or future profitability claim. No candidate activation."
        ),
    }

    def save():
        (args.out / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def run(name, start, end, costs):
        result = run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=SEED,
            target_notional=SEED / 2,
            costs=costs,
            execution_rules=rules,
            strategy=definition(name),
            reinvest_profits=True,
            autonomous_spot=True,
        )
        print(name, start.isoformat(), costs.name, summary(result), flush=True)
        return result

    for name in CATALOGUE:
        payload["train"][name] = [
            summary(run(name, START.replace(year=y), START.replace(year=y + 1), STRESS_COSTS))
            for y in (2023, 2024)
        ]
        save()
    eligible = [
        name
        for name in CATALOGUE
        if name != "baseline"
        and all(
            D(r["return_pct"]) > 0
            and D(r["return_pct"]) >= D(b["return_pct"]) * D(".95")
            and D(r["dd_pct"]) <= D(b["dd_pct"])
            for r, b in zip(payload["train"][name], payload["train"]["baseline"], strict=True)
        )
    ]
    winner = max(
        eligible,
        key=lambda name: min(
            D(r["return_pct"]) / max(D(r["dd_pct"]), D(".01")) for r in payload["train"][name]
        ),
        default=None,
    )
    payload["training_eligible"] = eligible
    payload["frozen_winner"] = winner
    save()
    # Other rejected candidates are visible diagnostics, never selected on these runs.
    for label, start in (("full", START), ("last_year", START.replace(year=2025))):
        for name in ("original_v8", *CATALOGUE):
            scenarios = {c.name: run(name, start, END, c) for c in (CURRENT_COSTS, STRESS_COSTS)}
            payload[label][name] = {k: summary(v) for k, v in scenarios.items()}
            if name in ("original_v8", "baseline", winner):
                report = write_report_bundle(
                    scenarios=scenarios,
                    output_root=args.out / "reports" / label / name,
                    config_sha256=hashlib.sha256(
                        json.dumps(definition(name).config_payload(), sort_keys=True).encode()
                    ).hexdigest(),
                    code_commit="RESEARCH_NO_PROMOTION",
                    report_start_utc=start,
                    report_end_utc=END,
                    strategy=definition(name),
                    history_data=continuity_manifest_data(history),
                    trading_settings={
                        "auto_budget_enabled": True,
                        "autonomous_performance_enabled": True,
                        "slot_count": 2,
                    },
                )
                payload[label][name]["report"] = str(report)
            save()
    checks = {}
    if winner:
        for costs in ("current", "stress"):
            full = payload["full"][winner][costs]
            anchor = payload["full"]["baseline"][costs]
            original = payload["full"]["original_v8"][costs]
            checks["full_" + costs] = D(full["return_pct"]) >= D(anchor["return_pct"]) * D(
                ".95"
            ) and D(full["dd_pct"]) <= D(original["dd_pct"]) * D(".8")
            last = payload["last_year"][winner][costs]
            reference = payload["last_year"]["baseline"][costs]
            checks["last_year_" + costs] = D(last["return_pct"]) >= D(
                reference["return_pct"]
            ) and D(last["dd_pct"]) <= D(reference["dd_pct"])
    payload["checks"] = checks
    payload["accepted"] = bool(winner) and all(checks.values())
    save()
    print("DONE", winner, payload["accepted"], flush=True)


if __name__ == "__main__":
    main()

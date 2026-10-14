"""Predeclared complete protection packages; no credentials, runtime or network replacement."""

import argparse
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

from protected_portfolio_research_20261012 import run_shared_portfolio_backtest
from research_coin_policies_20261011 import END, SEED, START, SnapshotOnly, summary

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

CATALOGUE = {
    "baseline": {},
    "protect20": {
        "reserve_fraction": "0.10",
        "symbol_cap_fraction": "0.50",
        "stop_fraction": "0.20",
        "halt_dd_pct": "20",
    },
    "protect25": {
        "reserve_fraction": "0.10",
        "symbol_cap_fraction": "0.50",
        "stop_fraction": "0.20",
        "halt_dd_pct": "25",
    },
    "protect30": {
        "reserve_fraction": "0.10",
        "symbol_cap_fraction": "0.50",
        "stop_fraction": "0.20",
        "halt_dd_pct": "30",
    },
}
SELECTION = (
    "Fixed protection family, both training years stress-cost profitable and DD no higher "
    "than active DOGE50 baseline. Rank minimum worst training DD, then total training "
    "return; freeze winner before full/last-year. Full current end >=32000 USDC at "
    "same seed/window, DD lower in both costs, stress end >=90% baseline. Last year "
    "return and DD no worse in either cost. Previously examined history, no pristine "
    "holdout. Fully documented STOP-MARKET model; no native exchange execution proof. "
    "Service uptime, watchdog, notifications and news are NOT tested by candle replay."
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    strategy = strategy_definition("v8r")
    assert strategy.policy_for("DOGEUSDC").cmo_floor == 0.5
    rules = {}
    with CandleStore(args.data / "hixton-usdc.sqlite3", read_only=True) as store:
        for symbol in strategy.symbols:
            r = store.load_symbol_rules(symbol)
            rules[symbol] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
    history = load_continuity_history(
        strategy=strategy,
        report_start_utc=START,
        report_end_utc=END,
        execution_rules=rules,
        native_database_path=args.data / "hixton-usdc.sqlite3",
        cache_path=args.data / "backtest-history.sqlite3",
        client=SnapshotOnly(),
    )
    payload = {
        "status": "RESEARCH_ONLY",
        "activated": False,
        "orders_sent": False,
        "base_strategy": strategy.version,
        "source_sha256": source_fingerprint(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "research_engine_sha256": hashlib.sha256(
            Path(__file__).with_name("protected_portfolio_research_20261012.py").read_bytes()
        ).hexdigest(),
        "catalogue": CATALOGUE,
        "selection": SELECTION,
        "seed": str(SEED),
        "period": [START.isoformat(), END.isoformat()],
        "data": continuity_manifest_data(history),
        "train": {},
        "full": {},
        "last_year": {},
    }

    def save():
        (args.out / "results.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    def run(name, start, end, cost):
        events = []
        result = run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=SEED,
            target_notional=SEED / 2,
            costs=cost,
            execution_rules=rules,
            strategy=strategy,
            reinvest_profits=True,
            autonomous_spot=True,
            research_protection=CATALOGUE[name],
            protection_events=events,
        )
        print(
            name,
            start.isoformat(),
            cost.name,
            summary(result),
            "halt",
            result.risk_halted_at_utc,
            flush=True,
        )
        return result, events

    for name in CATALOGUE:
        payload["train"][name] = [
            summary(run(name, START.replace(year=y), START.replace(year=y + 1), STRESS_COSTS)[0])
            for y in (2023, 2024)
        ]
        save()
    eligible = [
        name
        for name in CATALOGUE
        if name != "baseline"
        and all(
            D(r["return_pct"]) > 0 and D(r["dd_pct"]) <= D(b["dd_pct"])
            for r, b in zip(payload["train"][name], payload["train"]["baseline"], strict=True)
        )
    ]
    winner = min(
        eligible,
        key=lambda name: (
            max(D(r["dd_pct"]) for r in payload["train"][name]),
            -sum((D(r["return_pct"]) for r in payload["train"][name]), D(0)),
        ),
        default=None,
    )
    payload["training_eligible"] = eligible
    payload["frozen_winner"] = winner
    save()
    for label, start in (("full", START), ("last_year", START.replace(year=2025))):
        for name in CATALOGUE:
            results = {}
            events = {}
            for cost in (CURRENT_COSTS, STRESS_COSTS):
                result, audit = run(name, start, END, cost)
                results[cost.name] = result
                events[cost.name] = audit
            payload[label][name] = {c: summary(r) for c, r in results.items()}
            folder = write_report_bundle(
                scenarios=results,
                output_root=args.out / "reports" / label / name,
                config_sha256=hashlib.sha256(
                    json.dumps(
                        {"strategy": strategy.config_payload(), "protection": CATALOGUE[name]},
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
                code_commit="RESEARCH_NO_PROMOTION",
                report_start_utc=start,
                report_end_utc=END,
                strategy=strategy,
                history_data=continuity_manifest_data(history),
                trading_settings={
                    "auto_budget_enabled": True,
                    "autonomous_performance_enabled": True,
                    "slot_count": 2,
                    "research_protection": CATALOGUE[name],
                    "scope": "SIMULATED_PROTECTION_NOT_PRODUCT_RUNTIME",
                },
            )
            (folder / "protection-events.json").write_text(
                json.dumps(events, indent=2) + "\n", encoding="utf-8"
            )
            payload[label][name]["report"] = str(folder)
            save()
    checks = {}
    if winner:
        checks["normal_end_ge_32000"] = D(payload["full"][winner]["current"]["ending_usdc"]) >= D(
            32000
        )
        for cost in ("current", "stress"):
            r = payload["full"][winner][cost]
            b = payload["full"]["baseline"][cost]
            checks["full_dd_" + cost] = D(r["dd_pct"]) < D(b["dd_pct"])
            r = payload["last_year"][winner][cost]
            b = payload["last_year"]["baseline"][cost]
            checks["last_year_" + cost] = D(r["dd_pct"]) <= D(b["dd_pct"]) and D(
                r["return_pct"]
            ) >= D(b["return_pct"])
        checks["stress_capital_retention"] = D(
            payload["full"][winner]["stress"]["ending_usdc"]
        ) >= D(payload["full"]["baseline"]["stress"]["ending_usdc"]) * D(".9")
    payload["checks"] = checks
    payload["accepted"] = bool(winner) and all(checks.values())
    save()
    print("DONE", winner, payload["accepted"], flush=True)


if __name__ == "__main__":
    main()

"""Exact weighted-second-tranche research; no runtime source or account changes."""

import argparse
import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

from research_coin_policies_20261011 import END, SEED, START, SnapshotOnly, summary
from weighted_tranche_portfolio_20261013 import run_shared_portfolio_backtest

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

CATALOGUE = {
    "baseline": {"weights": (), "dd_trigger": "0"},
    "A_50_25_25": {"weights": (10, 5, 5), "dd_trigger": "0"},
    "B_50_30_20": {"weights": (10, 6, 4), "dd_trigger": "0"},
    "C_50_20_15_15": {"weights": (10, 4, 3, 3), "dd_trigger": "0"},
    "A_DD10": {"weights": (10, 5, 5), "dd_trigger": "10"},
    "A_DD15": {"weights": (10, 5, 5), "dd_trigger": "15"},
}
PROBE_SEED = SEED
SELECTION = (
    "Six cases predeclared before results: active DOGE50 baseline, A/B/C weighted "
    "second-tranche split, A conditional previous CLOSED DD>=10 or >=15%. Original "
    "full first half retained; no enough simultaneously VALID fresh signals -> native "
    "fallback, including lone Core both tranches. Also split remaining half only if "
    "one intact 50% tranche remains and enough valid new alternatives exist. No "
    "rebalancing owned quantities or synthetic free capital. ATR075 unchanged. "
    "Two chronological fresh-account stress training years with SAME original seed "
    "1092.05773944. >=3 cycles, no greater DD each year, return>=85% positive baseline "
    "or no worse negative baseline. Freeze winner by lowest worst DD then highest "
    "summed return before full/final year. Full normal+stress: ending capital>=own "
    "baseline AND DD strictly lower both costs; last year fresh SAME seed: return/DD "
    "no worse both costs. Previously examined history, not unseen holdout. "
    "20 INTERNAL capacity units mean 100% budget, NOT 20 product slots or positions. "
    "completed_slot_trades/max_concurrent_positions in native weighted diagnostics "
    "count units, NOT asset count; use completed_trades and allocation CSV distinct_coins. "
    "No correlation trigger guessed, no SUI/UNI activation, no BNB scenario added. "
    "No Paper/Live promotion proof, no activation or orders."
)


def audit_summary(audit):
    return {
        "max_actual_distinct_coins": max(r["distinct_coins"] for r in audit),
        "ledger_capacity_units": audit[0]["ledger_capacity_units"],
        "max_occupied_units": max(r["occupied_units"] for r in audit),
        "bars_three_or_more_coins": sum(r["distinct_coins"] >= 3 for r in audit),
        "bars_four_coins": sum(r["distinct_coins"] >= 4 for r in audit),
        "existing_positions_never_resized": all(r["existing_positions_unchanged"] for r in audit),
        "cash_never_negative": all(D(r["cash"]) >= 0 for r in audit),
    }


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
        "engine_sha256": hashlib.sha256(
            Path(__file__).with_name("weighted_tranche_portfolio_20261013.py").read_bytes()
        ).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "catalogue": CATALOGUE,
        "selection": SELECTION,
        "full_seed": str(SEED),
        "training_and_final_year_probe_seed": str(PROBE_SEED),
        "period": [START.isoformat(), END.isoformat()],
        "data": continuity_manifest_data(history),
        "train": {},
        "full": {},
        "last_year_probe": {},
    }

    def save():
        (args.out / "results.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    save()

    def run(name, start, end, cost, seed):
        audit = []
        events = []
        result = run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=seed,
            target_notional=seed / 2,
            costs=cost,
            execution_rules=rules,
            strategy=strategy,
            reinvest_profits=True,
            autonomous_spot=True,
            research_weights=tuple(CATALOGUE[name]["weights"]),
            research_dd_trigger_pct=D(CATALOGUE[name]["dd_trigger"]),
            allocation_audit=audit,
            allocation_events=events,
        )
        if name == "baseline" and start == START and end == END:
            assert result.metrics.ending_equity == D(
                {"current": "32469.38840320931655000000", "stress": "22817.4864778155955000000"}[
                    cost.name
                ]
            )
        row = summary(result)
        row["allocation"] = audit_summary(audit)
        row["planned_split_count"] = len(events)
        row["filled_split_count"] = sum(
            len(e["actual_new_symbols"]) >= len(e["planned_units"]) for e in events
        )
        print(
            name,
            start.isoformat(),
            cost.name,
            "seed",
            seed,
            "end",
            row["ending_usdc"],
            "DD",
            row["dd_pct"],
            "coins",
            row["allocation"]["max_actual_distinct_coins"],
            flush=True,
        )
        return result, audit, row, events

    for name in CATALOGUE:
        payload["train"][name] = []
        for year in (2023, 2024):
            _, _, row, _ = run(
                name,
                START.replace(year=year),
                START.replace(year=year + 1),
                STRESS_COSTS,
                PROBE_SEED,
            )
            payload["train"][name].append(row)
            save()
    eligible = [
        name
        for name in CATALOGUE
        if name != "baseline"
        and all(
            r["trades"] >= 3
            and D(r["dd_pct"]) <= D(b["dd_pct"])
            and D(r["return_pct"])
            >= (D(b["return_pct"]) * D(".85") if D(b["return_pct"]) > 0 else D(b["return_pct"]))
            for r, b in zip(payload["train"][name], payload["train"]["baseline"], strict=True)
        )
    ]
    winner = min(
        eligible,
        key=lambda n: (
            max(D(r["dd_pct"]) for r in payload["train"][n]),
            -sum((D(r["return_pct"]) for r in payload["train"][n]), D(0)),
        ),
        default=None,
    )
    payload["training_eligible"] = eligible
    payload["frozen_winner"] = winner
    save()
    print("FROZEN_WINNER", winner, eligible, flush=True)
    for label, start, seed in (
        ("full", START, SEED),
        ("last_year_probe", START.replace(year=2025), PROBE_SEED),
    ):
        for name in CATALOGUE:
            results, audits, all_events = {}, {}, {}
            payload[label][name] = {}
            for cost in (CURRENT_COSTS, STRESS_COSTS):
                result, audit, row, events = run(name, start, END, cost, seed)
                results[cost.name], audits[cost.name], all_events[cost.name] = result, audit, events
                payload[label][name][cost.name] = row
                save()
            folder = write_report_bundle(
                scenarios=results,
                output_root=args.out / "reports" / label / name,
                config_sha256=hashlib.sha256(
                    json.dumps(
                        {
                            "strategy": strategy.config_payload(),
                            "research_tranche_weights": CATALOGUE[name],
                        },
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
                    "research_tranche_weights": CATALOGUE[name],
                    "scope": "WEIGHTED_SECOND_TRANCHE_RESEARCH_NOT_PAPER_OR_LIVE",
                    "dd_basis": "PREVIOUS_CLOSED_EQUITY_AND_FULL_HIGH_WATER",
                    "capacity_unit_denominator": 20,
                    "units_are_not_positions": True,
                    "seed": str(seed),
                    "no_resizing": True,
                },
            )
            for cost, audit in audits.items():
                with (folder / f"allocation-{cost}.csv").open(
                    "w", newline="", encoding="utf-8"
                ) as f:
                    writer = csv.DictWriter(f, fieldnames=list(audit[0]))
                    writer.writeheader()
                    for row in audit:
                        writer.writerow(
                            {**row, "positions": json.dumps(row["positions"], sort_keys=True)}
                        )
            (folder / "allocation-events.json").write_text(
                json.dumps(all_events, indent=2) + "\n", encoding="utf-8"
            )
            payload[label][name]["report"] = str(folder)
            save()
    checks = {}
    if winner:
        for cost in ("current", "stress"):
            checks["full_capital_at_least_baseline_" + cost] = D(
                payload["full"][winner][cost]["ending_usdc"]
            ) >= D(payload["full"]["baseline"][cost]["ending_usdc"])
        for cost in ("current", "stress"):
            r, b = payload["full"][winner][cost], payload["full"]["baseline"][cost]
            checks["full_dd_lower_" + cost] = D(r["dd_pct"]) < D(b["dd_pct"])
            r, b = (
                payload["last_year_probe"][winner][cost],
                payload["last_year_probe"]["baseline"][cost],
            )
            checks["last_year_probe_" + cost] = D(r["dd_pct"]) <= D(b["dd_pct"]) and D(
                r["return_pct"]
            ) >= D(b["return_pct"])
        checks["stress_capital_retention"] = D(
            payload["full"][winner]["stress"]["ending_usdc"]
        ) >= D(payload["full"]["baseline"]["stress"]["ending_usdc"])
    payload["checks"] = checks
    payload["accepted"] = bool(winner) and all(checks.values())
    save()
    print("DONE", winner, payload["accepted"], checks, flush=True)


if __name__ == "__main__":
    main()

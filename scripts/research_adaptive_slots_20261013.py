"""Predeclared adaptive equity thresholds; market-only, research-only, no promotion."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal as D
from pathlib import Path

from adaptive_capacity_research_20261013 import run_shared_portfolio_backtest
from research_coin_policies_20261011 import END, SEED, START, SnapshotOnly, summary

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

CATALOGUE = {
    "baseline": (),
    "four10": (("10000", 4),),
    "four15": (("15000", 4),),
    "four20": (("20000", 4),),
    "six10": (("10000", 4), ("30000", 6)),
    "six15": (("15000", 4), ("30000", 6)),
    "six20": (("20000", 4), ("30000", 6)),
}
PROBE_SEED = D("20000")
SELECTION = (
    "Declared before replay. Two separate chronological training years use a fresh "
    "20000-USDC simulated account and stress costs to EXERCISE the proposed capital "
    "levels; a 1092-USDC fresh account might never cross these thresholds in one year. "
    "Each training year: >=3 trades, DD no greater than baseline, return >=85% of "
    "positive baseline return or no worse than negative baseline. Select lowest "
    "worst training DD, then highest summed training return, freeze before validation. "
    "Full 3-year replay uses ORIGINAL 1092.05773944 seed: normal end >=32000, DD lower "
    "in both cost cases, stress end >=90% baseline. Final-year fresh capital PROBE "
    "uses 20000 (not appended full equity): return and DD no worse than its own "
    "same-seed baseline in both costs. Already examined history, NOT an unseen holdout. "
    "Capacity basis is preceding CLOSED candle equity; no automatic resizing of "
    "existing positions, no forced signal/trade, no imaginary cash release. "
    "Capacity>=4: one slot per NEW distinct coin; capacity=2 preserves ranked-repeat. "
    "ATR075 and Core absolute priority retained. Research-only, NOT runtime parity proof."
)


def audit_summary(audit):
    counts = Counter(r["target_slots"] for r in audit)
    return {
        "max_actual_distinct_coins": max(r["distinct_coins"] for r in audit),
        "max_occupied_slots": max(r["occupied_slots"] for r in audit),
        "bars_at_capacity": dict(counts),
        "bars_four_or_more_coins": sum(r["distinct_coins"] >= 4 for r in audit),
        "bars_six_coins": sum(r["distinct_coins"] >= 6 for r in audit),
        "max_coin_weight_pct": str(max(D(r["largest_coin_weight_pct"]) for r in audit)),
        "existing_positions_never_resized": all(r["existing_positions_unchanged"] for r in audit),
        "cash_never_negative": all(D(r["cash"]) >= 0 for r in audit),
        "capacity_transitions": [
            {
                k: row[k]
                for k in (
                    "time_utc",
                    "capacity_basis_equity",
                    "target_slots",
                    "occupied_slots",
                    "distinct_coins",
                )
            }
            for i, row in enumerate(audit)
            if i == 0 or row["target_slots"] != audit[i - 1]["target_slots"]
        ],
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
            Path(__file__).with_name("adaptive_capacity_research_20261013.py").read_bytes()
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
            research_capacity_schedule=tuple((D(t), n) for t, n in CATALOGUE[name]),
            capacity_audit=audit,
        )
        row = summary(result)
        row["capacity"] = audit_summary(audit)
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
            row["capacity"]["max_actual_distinct_coins"],
            flush=True,
        )
        return result, audit, row

    for name in CATALOGUE:
        payload["train"][name] = []
        for year in (2023, 2024):
            _, _, row = run(
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
            results, audits = {}, {}
            payload[label][name] = {}
            for cost in (CURRENT_COSTS, STRESS_COSTS):
                result, audit, row = run(name, start, END, cost, seed)
                results[cost.name], audits[cost.name] = result, audit
                payload[label][name][cost.name] = row
                save()
            folder = write_report_bundle(
                scenarios=results,
                output_root=args.out / "reports" / label / name,
                config_sha256=hashlib.sha256(
                    json.dumps(
                        {
                            "strategy": strategy.config_payload(),
                            "research_capacity_schedule": CATALOGUE[name],
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
                    "research_capacity_schedule": CATALOGUE[name],
                    "scope": "ISOLATED_ADAPTIVE_SLOT_PROTOTYPE_NOT_PAPER_OR_LIVE",
                    "capacity_basis": "PREVIOUS_CLOSED_BAR_EQUITY",
                    "seed": str(seed),
                    "no_resizing": True,
                },
            )
            for cost, audit in audits.items():
                with (folder / f"capacity-{cost}.csv").open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(audit[0]))
                    writer.writeheader()
                    for row in audit:
                        writer.writerow(
                            {**row, "positions": json.dumps(row["positions"], sort_keys=True)}
                        )
            payload[label][name]["report"] = str(folder)
            save()
    checks = {}
    if winner:
        checks["normal_end_ge_32000"] = D(payload["full"][winner]["current"]["ending_usdc"]) >= D(
            32000
        )
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
        ) >= D(payload["full"]["baseline"]["stress"]["ending_usdc"]) * D(".9")
    payload["checks"] = checks
    payload["accepted"] = bool(winner) and all(checks.values())
    save()
    print("DONE", winner, payload["accepted"], checks, flush=True)


if __name__ == "__main__":
    main()

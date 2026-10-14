"""Exact-engine verification of the three GPT night hypotheses. No runtime changes."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal as D
from pathlib import Path

from night_candidates_portfolio_20261013 import run_shared_portfolio_backtest
from research_coin_policies_20261011 import END, SEED, START, SnapshotOnly, summary
from research_volatility_budget_20261012 import definition as volatility_definition

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

CATALOGUE = {
    "baseline": {"schedule": (), "single_slot_symbols": ()},
    "four15_eight28": {"schedule": (("15000", 4), ("28000", 8)), "single_slot_symbols": ()},
    "four25_eight28": {"schedule": (("25000", 4), ("28000", 8)), "single_slot_symbols": ()},
    "four20_selective": {
        "schedule": (("20000", 4),),
        "single_slot_symbols": ("DOGEUSDC", "BNBUSDC", "XRPUSDC"),
    },
}
PROBE_SEED = D("20000")
SELECTION = (
    "Catalogue fixed from the user-provided night results. Two independent strategy "
    "anchors: exact LINK8 without ATR075/DOGE50 and current active DOGE50. Each anchor "
    "uses its own native baseline. Chronological two-year training at stress costs, "
    "fresh 20000-USDC capital to exercise thresholds. Eligibility requires >=3 "
    "completed cycles, DD no worse each year, >=85% positive baseline return or "
    "no worse negative baseline. Freeze lowest worst-fold DD, then sum return BEFORE "
    "full/final-year replay. Full three years at original seed1092.05773944: ending "
    "capital at least same-anchor baseline and DD strictly lower in BOTH costs. "
    "Final-year fresh 20000 capital probe: return and DD no worse than its own baseline "
    "in both costs. Historical selection is already examined, NOT unseen holdout. "
    "Capacity uses previous CLOSED equity (can decrease); existing positions never "
    "resized. Above two slots: new positions strictly one per valid distinct coin. "
    "Selective third hypothesis forbids second DOGE/BNB/XRP tranche at ALL equity "
    "levels; other below20k ranked-repeat behavior unchanged. No SUI/UNI activation, "
    "no invented market-breadth filters: their formulas and raw proxy data were not supplied. "
    "No claim to reproduce proxy +15/+50bps without their per-side/per-trade definition. "
    "Normal and Stress use canonical CostModels, no future signal or cash fabrication. "
    "This is engineering research, not Paper/Live promotion or execution proof."
)


def audit_summary(audit):
    counts = Counter(r["target_slots"] for r in audit)
    return {
        "max_actual_distinct_coins": max(r["distinct_coins"] for r in audit),
        "max_occupied_slots": max(r["occupied_slots"] for r in audit),
        "bars_at_capacity": dict(counts),
        "bars_four_or_more_coins": sum(r["distinct_coins"] >= 4 for r in audit),
        "bars_six_coins": sum(r["distinct_coins"] >= 6 for r in audit),
        "bars_eight_coins": sum(r["distinct_coins"] >= 8 for r in audit),
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
    parser.add_argument("--anchor", choices=("link8", "doge50"), required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    strategy = (
        volatility_definition("link_only") if args.anchor == "link8" else strategy_definition("v8r")
    )
    assert strategy.parameters_for("LINKUSDC").vidya_length == 8
    if args.anchor == "link8":
        assert (
            strategy.entry_atr_target_fraction is None
            and strategy.policy_for("DOGEUSDC").cmo_floor == 0.2
        )
    else:
        assert (
            strategy.entry_atr_target_fraction == "0.0075"
            and strategy.policy_for("DOGEUSDC").cmo_floor == 0.5
        )
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
        "anchor": args.anchor,
        "unverified_proxy_claims": {
            "four15_eight28": [41575, 36.47],
            "four25_eight28": [43127, 43.58],
            "all15_four20_selective": [45060, 43.58],
        },
        "proxy_raw_data_provided": False,
        "source_sha256": source_fingerprint(),
        "engine_sha256": hashlib.sha256(
            Path(__file__).with_name("night_candidates_portfolio_20261013.py").read_bytes()
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
            research_capacity_schedule=tuple((D(t), n) for t, n in CATALOGUE[name]["schedule"]),
            research_single_slot_symbols=frozenset(CATALOGUE[name]["single_slot_symbols"]),
            capacity_audit=audit,
        )
        if name == "baseline" and start == START and end == END and seed == SEED:
            expected = {
                "link8": {
                    "current": "35855.55093575210370000000",
                    "stress": "21956.5504456338837000000",
                },
                "doge50": {
                    "current": "32469.38840320931655000000",
                    "stress": "22817.4864778155955000000",
                },
            }[args.anchor][cost.name]
            assert result.metrics.ending_equity == D(expected), (
                args.anchor,
                cost.name,
                result.metrics.ending_equity,
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
                    "scope": "EXACT_ENGINE_NIGHT_HYPOTHESIS_NOT_PAPER_OR_LIVE",
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

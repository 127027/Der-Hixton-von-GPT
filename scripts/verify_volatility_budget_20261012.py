"""Final-source reproduction, without private accounts, keys or orders."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research_coin_policies_20261011 import END, SEED, START, SnapshotOnly, summary
from research_volatility_budget_20261012 import definition

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--broad", type=Path, required=True)
    parser.add_argument("--refined", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    broad = json.loads(args.broad.read_text())
    refined = json.loads(args.refined.read_text())
    rules = {}
    base = definition("baseline")
    with CandleStore(args.data / "hixton-usdc.sqlite3", read_only=True) as store:
        for sym in base.symbols:
            r = store.load_symbol_rules(sym)
            rules[sym] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
    history = load_continuity_history(
        strategy=base,
        report_start_utc=START,
        report_end_utc=END,
        execution_rules=rules,
        native_database_path=args.data / "hixton-usdc.sqlite3",
        cache_path=args.data / "backtest-history.sqlite3",
        client=SnapshotOnly(),
    )
    proof = {
        "status": "RESEARCH_ONLY_NOT_ACTIVATED",
        "source_sha256": source_fingerprint(),
        "strict_acceptance": False,
        "cases": {},
        "data": continuity_manifest_data(history),
    }
    for label, start in (("full", START), ("validation", START.replace(year=2025))):
        names = (
            ("baseline", "link_only", "atr0075", "atr006")
            if label == "full"
            else ("atr0075", "atr006")
        )
        for name in names:
            scenarios = {}
            for costs in (CURRENT_COSTS, STRESS_COSTS):
                result = run_shared_portfolio_backtest(
                    candles_by_symbol=history.candles_by_symbol,
                    report_start_utc=start,
                    report_end_utc=END,
                    starting_cash=SEED,
                    target_notional=SEED / 2,
                    costs=costs,
                    execution_rules=rules,
                    strategy=definition(name),
                    reinvest_profits=True,
                    autonomous_spot=True,
                )
                stats = summary(result)
                expected = (refined if name == "atr006" else broad)[label][name][costs.name]
                assert stats == expected, (label, name, costs.name, stats, expected)
                scenarios[costs.name] = result
                proof["cases"][f"{label}/{name}/{costs.name}"] = {
                    "metrics": stats,
                    "matches_experiment": True,
                }
                print("VERIFIED", label, name, costs.name, flush=True)
            report = write_report_bundle(
                scenarios=scenarios,
                output_root=args.out / "reports" / label / name,
                config_sha256=hashlib.sha256(
                    json.dumps(definition(name).config_payload(), sort_keys=True).encode()
                ).hexdigest(),
                code_commit="FINAL_RESEARCH_SOURCE_IDENTIFIED_BY_SHA256_NO_PROMOTION",
                report_start_utc=start,
                report_end_utc=END,
                strategy=definition(name),
                history_data=continuity_manifest_data(history),
                trading_settings={
                    "auto_budget_enabled": True,
                    "autonomous_performance_enabled": True,
                    "slot_count": 2,
                },
                capital_source={
                    "kind": "DATED_SIMULATION_REFERENCE_NO_PRIVATE_API_ACCESS",
                    "starting_usdc": str(SEED),
                },
            )
            proof["cases"][f"{label}/{name}/report"] = str(report)
            (args.out / "proof.json").write_text(
                json.dumps(proof, indent=2) + "\n", encoding="utf-8"
            )
    proof["all_cases_matched"] = True
    (args.out / "proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""Reproduce accepted coin experiments with the final research implementation."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from research_coin_policies_20261011 import (
    END,
    START,
    SnapshotOnly,
    profile_variant,
    summary,
)

from hixton.backtest.coin_review import diagnose
from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.reporting import source_fingerprint
from hixton.data.storage import CandleStore
from hixton.domain.satellite_layer import SATELLITE_PROFILE_BY_SYMBOL
from hixton.domain.versions import strategy_definition


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--experiments", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    base = strategy_definition("v8")
    profiles = {p.symbol: p for p in base.coin_profiles}
    rules = {}
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
        "status": "RESEARCH_ONLY",
        "source_sha256": source_fingerprint(),
        "research_script_sha256": hashlib.sha256(
            Path(__file__).with_name("research_coin_policies_20261011.py").read_bytes()
        ).hexdigest(),
        "installed": False,
        "orders_sent": False,
        "data": continuity_manifest_data(history),
        "baseline": {},
        "verified_candidates": {},
    }

    def run(sym, profile, start, cost):
        from decimal import Decimal

        return run_single_backtest(
            symbol=sym,
            candles=history.candles_by_symbol[sym],
            report_start_utc=start,
            report_end_utc=END,
            starting_cash=Decimal("1100"),
            target_notional=Decimal("1100"),
            costs=cost,
            execution_rules=rules[sym],
            strategy_parameters=profile.parameters,
            trade_policy=profile.trade_policy,
            strategy_semantics=base.semantics_for(sym),
            strategy_version=base.version,
            satellite_profile=SATELLITE_PROFILE_BY_SYMBOL.get(sym),
            apply_risk_limits=True,
        )

    def save():
        (args.out / "verification.json").write_text(
            json.dumps(proof, default=str, indent=2) + "\n", encoding="utf-8"
        )

    for sym in base.symbols:
        proof["baseline"][sym] = {}
        for cost in (CURRENT_COSTS, STRESS_COSTS):
            result = run(sym, profiles[sym], START, cost)
            proof["baseline"][sym][cost.name] = summary(result)
            if cost == CURRENT_COSTS:
                proof["baseline"][sym]["diagnosis"] = diagnose(
                    result, history.candles_by_symbol[sym]
                )
        print("BASELINE", sym, flush=True)
        save()
    for experiment in args.experiments:
        payload = json.loads(experiment.read_text())
        family = payload.get("family", "policies")
        frozen = {s: r["selected"] for s, r in payload["coins"].items()}
        assert (
            hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
            == payload["frozen_training_selection_sha256"]
        )
        for sym in payload["accepted_coins"]:
            row = payload["coins"][sym]
            selected = profile_variant(profiles[sym], row["selected"], family)
            key = f"{family}/{sym}/{row['selected']}"
            candidate = {"profile": asdict(selected), "full": {}, "validation_matches": {}}
            for cost in (CURRENT_COSTS, STRESS_COSTS):
                result = run(sym, selected, START.replace(year=2025), cost)
                assert summary(result) == row["validation"][row["selected"]][cost.name]
                candidate["validation_matches"][cost.name] = True
                candidate["full"][cost.name] = summary(run(sym, selected, START, cost))
            proof["verified_candidates"][key] = candidate
            print("VERIFIED", key, candidate, flush=True)
            save()
    proof["all_accepted_coin_candidates_reproduced"] = True
    save()


if __name__ == "__main__":
    main()

"""Risk-sized LINK research on a frozen market snapshot; no runtime activation."""

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
from hixton.domain.versions import strategy_definition

CATALOGUE = {
    "baseline": None,
    "link_only": None,
    "atr005": ".005",
    "atr0075": ".0075",
    "atr010": ".01",
    "atr015": ".015",
    "atr020": ".02",
}
RISK_CATALOGUE = {
    "baseline": None,
    "link_only": None,
    "atr005": ".005",
    "atr006": ".006",
    "atr00625": ".00625",
    "atr0065": ".0065",
    "atr0075": ".0075",
}
FILLER_CATALOGUE = {
    "baseline": None,
    "link_only": None,
    "near_off": None,
    "near_cmo30": None,
    "near_cmo40": None,
    "near_cmo50": None,
}
KNOWN_CANDIDATES = {**CATALOGUE, **RISK_CATALOGUE, **FILLER_CATALOGUE}
SELECTION = (
    "Two chronological fresh-account training years at stress costs. Both years "
    "must remain profitable, retain >=75% baseline return and have DD <=80% "
    "baseline. Rank by highest worst-fold return/DD. Freeze winner before final "
    "year; reject on either cost case if final-year return worsens negative "
    "baseline or retains <80% positive baseline, or DD increases. Full-period "
    "acceptance additionally requires >=80% baseline return and DD <=80% baseline "
    "in both cost cases. This already-examined history is not an unseen holdout."
)


def definition(name):
    base = strategy_definition("v8")
    if name == "baseline":
        return base
    if name not in KNOWN_CANDIDATES:
        raise ValueError("unknown volatility candidate")
    profiles = tuple(
        replace(p, parameters=replace(p.parameters, vidya_length=8))
        if p.symbol == "LINKUSDC"
        else p
        for p in base.coin_profiles
    )
    if name.startswith("near_cmo"):
        profiles = tuple(
            replace(
                p,
                trade_policy=replace(
                    p.trade_policy, cmo_floor=max(p.trade_policy.cmo_floor, int(name[-2:]) / 100)
                ),
            )
            if p.symbol == "NEARUSDC"
            else p
            for p in profiles
        )
    return replace(
        base,
        coin_profiles=profiles,
        paper_approved=False,
        entry_atr_target_fraction=KNOWN_CANDIDATES[name],
        active_shared_satellites=tuple(
            s for s in base.active_shared_satellites if name != "near_off" or s != "NEARUSDC"
        ),
        version="HIXTON-V8-VOLATILITY-RESEARCH-" + name,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--family", choices=("volatility", "volatility_risk", "fillers"), default="volatility"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    if args.family != "volatility":
        CATALOGUE.clear()
        CATALOGUE.update(RISK_CATALOGUE if args.family == "volatility_risk" else FILLER_CATALOGUE)
    base = definition("baseline")
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
    payload = {
        "status": "RESEARCH_ONLY",
        "installed": False,
        "orders_sent": False,
        "kind": "TEMPORAL_REJECTION_ON_PREVIOUSLY_EXAMINED_HISTORY",
        "source_sha256": source_fingerprint(),
        "selection": SELECTION,
        "period": [START.isoformat(), END.isoformat()],
        "seed": str(SEED),
        "catalogue": CATALOGUE,
        "family": args.family,
        "data": continuity_manifest_data(history),
        "train": {},
        "full": {},
        "validation": {},
    }
    if args.family == "volatility_risk":
        payload["selection"] = SELECTION.replace(
            "Rank by highest worst-fold return/DD.",
            "Adaptive risk-priority refinement after the broad family: rank lowest "
            "worst training DD, then highest summed training return. Full/last-year "
            "history was previously inspected; no pristine holdout claim.",
        )
    elif args.family == "fillers":
        payload["selection"] = (
            "Against LINK-only: two stress-cost training years retain >=95% reference "
            "return with no worse DD. Rank highest worst-fold return/DD. Freeze before "
            "final year. Full and last year, both cost cases: return >= reference and "
            "DD <= reference. Previously examined history, not unseen holdout."
        )

    def save():
        (args.out / "results.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

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
    eligible = []
    reference_name = "link_only" if args.family == "fillers" else "baseline"
    for name, rows in payload["train"].items():
        if name not in ("baseline", "link_only") and all(
            D(r["return_pct"]) > 0
            and D(r["return_pct"])
            >= D(b["return_pct"]) * (D(".95") if args.family == "fillers" else D(".75"))
            and D(r["dd_pct"]) <= D(b["dd_pct"]) * (D(1) if args.family == "fillers" else D(".80"))
            for r, b in zip(rows, payload["train"][reference_name], strict=True)
        ):
            eligible.append(name)
    payload["training_eligible"] = eligible
    winner = (
        max(
            eligible,
            key=lambda n: min(
                D(r["return_pct"]) / max(D(r["dd_pct"]), D(".01")) for r in payload["train"][n]
            ),
        )
        if eligible
        else None
    )
    payload["frozen_winner"] = winner
    if args.family == "volatility_risk" and eligible:
        winner = min(
            eligible,
            key=lambda n: (
                max(D(r["dd_pct"]) for r in payload["train"][n]),
                -sum((D(r["return_pct"]) for r in payload["train"][n]), D(0)),
            ),
        )
        payload["frozen_winner"] = winner
    save()
    for label, start in (("full", START), ("validation", START.replace(year=2025))):
        for name in dict.fromkeys(("baseline", "link_only", winner)):
            if name is None:
                continue
            scenarios = {c.name: run(name, start, END, c) for c in (CURRENT_COSTS, STRESS_COSTS)}
            payload[label][name] = {k: summary(v) for k, v in scenarios.items()}
            report = write_report_bundle(
                scenarios=scenarios,
                output_root=args.out / "reports" / label / name,
                config_sha256=hashlib.sha256(
                    json.dumps(definition(name).config_payload(), sort_keys=True).encode()
                ).hexdigest(),
                code_commit="RESEARCH_SOURCE_IDENTIFIED_BY_SHA256_NO_PROMOTION",
                report_start_utc=start,
                report_end_utc=END,
                strategy=definition(name),
                history_data=continuity_manifest_data(history),
                trading_settings={
                    "auto_budget_enabled": True,
                    "autonomous_performance_enabled": True,
                    "slot_count": 2,
                    "entry_atr_target_fraction": CATALOGUE[name],
                },
                capital_source={
                    "kind": "DATED_SIMULATION_REFERENCE_NO_PRIVATE_API_ACCESS",
                    "starting_usdc": str(SEED),
                },
            )
            payload[label][name]["report"] = str(report)
            save()
    checks = {}
    if winner:
        for label in ("full", "validation"):
            for cost in ("current", "stress"):
                r, b = payload[label][winner][cost], payload[label][reference_name][cost]
                threshold = (
                    D(b["return_pct"]) * D(".8") if D(b["return_pct"]) > 0 else D(b["return_pct"])
                )
                checks[label + "_" + cost] = D(r["return_pct"]) >= threshold and D(
                    r["dd_pct"]
                ) <= D(b["dd_pct"]) * (D(".8") if label == "full" else D(1))
                if args.family == "fillers":
                    checks[label + "_" + cost] = D(r["return_pct"]) >= D(b["return_pct"]) and D(
                        r["dd_pct"]
                    ) <= D(b["dd_pct"])
    payload["checks"] = checks
    payload["accepted"] = bool(winner) and all(checks.values())
    save()
    print("DONE", winner, payload["accepted"], flush=True)


if __name__ == "__main__":
    main()

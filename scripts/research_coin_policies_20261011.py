"""Native per-coin policy research, followed by shared-portfolio rejection.

No account, credential, order, activation or runtime-state access. Uses a
market-only snapshot and refuses replacement data from the network. Selection
is frozen before the final-year comparisons; examined history is not an unseen
holdout. The current V8 strategy and V6 regression anchor are unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.satellite_layer import SATELLITE_PROFILE_BY_SYMBOL
from hixton.domain.versions import strategy_definition

START = datetime(2023, 10, 11, 19, tzinfo=UTC)
END = datetime(2026, 10, 11, 19, tzinfo=UTC)
SEED = D("1092.05773944")
CATALOGUE = (
    "baseline",
    "slope24",
    "slope72",
    "cmo40",
    "stop4",
    "trail6",
    "stop4_trail6",
    "slope24_trail6",
    "cmo40_trail6",
)
PARAMETER_CATALOGUE = (
    "baseline",
    "band80",
    "band120",
    "vidya75",
    "vidya125",
    "atr75",
    "atr125",
)
HYBRID_CATALOGUE = (
    "baseline",
    "band80_slope24",
    "band80_cmo40",
    "band80_stop4",
    "band120_slope24",
    "band120_trail6",
    "vidya125_trail6",
)
SELECTION = (
    "Two fresh-account training years, stress costs. Each year retains at least "
    "min(0, baseline return), has >=3 completed trades and no worse DD. Retain "
    ">=70% of summed positive baseline profit; worst training DD <=85% baseline. "
    "Select lowest worst DD, then highest summed return. Freeze selection before "
    "final year. Reject selected coin on either cost case if final-year DD "
    "increases or return retains <80% of positive baseline / worsens negative baseline."
)


def policy_variant(base, name):
    if name not in CATALOGUE:
        raise ValueError("unknown policy variant")
    if name == "baseline":
        return base
    return replace(
        base,
        slope_bars=max(
            base.slope_bars, 72 if "slope72" in name else 24 if "slope24" in name else 0
        ),
        cmo_floor=max(base.cmo_floor, 0.4 if "cmo40" in name else 0),
        stop_atr=min(base.stop_atr, 4)
        if "stop4" in name and base.stop_atr
        else 4
        if "stop4" in name
        else base.stop_atr,
        trail_atr=min(base.trail_atr, 6)
        if "trail6" in name and base.trail_atr
        else 6
        if "trail6" in name
        else base.trail_atr,
    )


def profile_variant(base, name, family):
    if family == "policies":
        return replace(base, trade_policy=policy_variant(base.trade_policy, name))
    if family == "hybrid":
        if name not in HYBRID_CATALOGUE:
            raise ValueError("unknown hybrid variant")
        if name == "baseline":
            return base
        parameter, policy = name.split("_")
        return replace(
            base,
            parameters=profile_variant(base, parameter, "parameters").parameters,
            trade_policy=policy_variant(base.trade_policy, policy),
        )
    if family != "parameters" or name not in PARAMETER_CATALOGUE:
        raise ValueError("unknown parameter variant")
    p = base.parameters
    changes = {}
    if name.startswith("band"):
        changes["band_multiplier"] = round(p.band_multiplier * int(name[4:]) / 100, 3)
    elif name.startswith("vidya"):
        changes["vidya_length"] = max(2, round(p.vidya_length * int(name[5:]) / 100))
    elif name.startswith("atr"):
        changes["atr_length"] = max(2, round(p.atr_length * int(name[3:]) / 100))
    return replace(base, parameters=replace(p, **changes))


def train_eligible(rows, baseline):
    if len(rows) != 2 or len(baseline) != 2:
        raise ValueError("exactly two chronological training folds required")
    if not all(
        r["trades"] >= 3
        and D(r["return_pct"]) >= min(D(0), D(b["return_pct"]))
        and D(r["dd_pct"]) <= D(b["dd_pct"])
        for r, b in zip(rows, baseline, strict=True)
    ):
        return False
    positive_baseline = sum((max(D(0), D(b["return_pct"])) for b in baseline), D(0))
    return sum((D(r["return_pct"]) for r in rows), D(0)) >= positive_baseline * D(".70") and max(
        D(r["dd_pct"]) for r in rows
    ) <= max(D(b["dd_pct"]) for b in baseline) * D(".85")


def validation_passes(candidate, baseline):
    for cost in ("current", "stress"):
        r, b = candidate[cost], baseline[cost]
        baseline_return = D(b["return_pct"])
        threshold = baseline_return * D(".80") if baseline_return > 0 else baseline_return
        if D(r["return_pct"]) < threshold or D(r["dd_pct"]) > D(b["dd_pct"]):
            return False
    return True


def summary(run):
    m = run.metrics
    return {
        "ending_usdc": str(m.ending_equity),
        "return_pct": str(m.return_pct),
        "dd_pct": str(m.max_drawdown_pct),
        "trades": m.completed_trades,
        "fees_usdc": str(m.total_fees),
        "profit_factor": str(m.profit_factor),
        "open_at_end": getattr(run, "open_position_at_end", None),
    }


class SnapshotOnly:
    def fetch_klines(self, *args, **kwargs):
        raise RuntimeError("snapshot incomplete; no network replacement allowed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--family", choices=("policies", "parameters", "hybrid"), default="policies"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    base = strategy_definition("v8")
    catalogue = {
        "policies": CATALOGUE,
        "parameters": PARAMETER_CATALOGUE,
        "hybrid": HYBRID_CATALOGUE,
    }[args.family]
    base_profiles = {p.symbol: p for p in base.coin_profiles}
    rules = {}
    with CandleStore(args.data / "hixton-usdc.sqlite3", read_only=True) as store:
        for sym in base.symbols:
            r = store.load_symbol_rules(sym)
            if r is None:
                raise ValueError(f"missing execution rules: {sym}")
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
        "installed": False,
        "orders_sent": False,
        "kind": "TEMPORAL_REJECTION_ON_PREVIOUSLY_EXAMINED_HISTORY",
        "source_sha256": source_fingerprint(),
        "base_strategy": base.version,
        "period": [START.isoformat(), END.isoformat()],
        "selection_rule": SELECTION,
        "catalogue": list(catalogue),
        "family": args.family,
        "research_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": continuity_manifest_data(history),
        "coins": {},
        "portfolio": {},
    }

    def save():
        (args.out / "results.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")

    def isolated(sym, profile, start, end, costs):
        return run_single_backtest(
            symbol=sym,
            candles=history.candles_by_symbol[sym],
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=D("1100"),
            target_notional=D("1100"),
            costs=costs,
            execution_rules=rules[sym],
            strategy_parameters=profile.parameters,
            trade_policy=profile.trade_policy,
            strategy_semantics=base.semantics_for(sym),
            strategy_version=base.version,
            satellite_profile=SATELLITE_PROFILE_BY_SYMBOL.get(sym),
            apply_risk_limits=True,
        )

    # All training decisions are completed and serialized before ANY validation.
    for sym in base.symbols:
        row = {"base_profile": asdict(base_profiles[sym]), "train": {}, "profiles": {}}
        seen = set()
        for name in catalogue:
            profile = profile_variant(base_profiles[sym], name, args.family)
            identity = (profile.parameters, profile.trade_policy)
            if identity in seen:
                continue
            seen.add(identity)
            row["profiles"][name] = asdict(profile)
            row["train"][name] = [
                summary(
                    isolated(
                        sym, profile, START.replace(year=y), START.replace(year=y + 1), STRESS_COSTS
                    )
                )
                for y in (2023, 2024)
            ]
        eligible = [
            name
            for name, rs in row["train"].items()
            if name != "baseline" and train_eligible(rs, row["train"]["baseline"])
        ]
        row["training_eligible"] = eligible
        row["selected"] = (
            min(
                eligible,
                key=lambda n: (
                    max(D(r["dd_pct"]) for r in row["train"][n]),
                    -sum((D(r["return_pct"]) for r in row["train"][n]), D(0)),
                    catalogue.index(n),
                ),
            )
            if eligible
            else "baseline"
        )
        proof["coins"][sym] = row
        save()
        print(sym, "TRAIN", row["selected"], "eligible", eligible, flush=True)
    frozen = {s: row["selected"] for s, row in proof["coins"].items()}
    proof["frozen_training_selection_sha256"] = hashlib.sha256(
        json.dumps(frozen, sort_keys=True).encode()
    ).hexdigest()
    save()
    for sym, row in proof["coins"].items():
        row["validation"] = {}
        for name in dict.fromkeys(("baseline", row["selected"])):
            profile = profile_variant(base_profiles[sym], name, args.family)
            row["validation"][name] = {
                c.name: summary(isolated(sym, profile, START.replace(year=2025), END, c))
                for c in (CURRENT_COSTS, STRESS_COSTS)
            }
        row["accepted"] = row["selected"] != "baseline" and validation_passes(
            row["validation"][row["selected"]], row["validation"]["baseline"]
        )
        row["effective_profile"] = row["profiles"][
            row["selected"] if row["accepted"] else "baseline"
        ]
        print(sym, "VALIDATION", row["selected"], row["accepted"], flush=True)
        save()
    assert frozen == {s: row["selected"] for s, row in proof["coins"].items()}
    effective = {
        s: profile_variant(
            base_profiles[s], r["selected"] if r["accepted"] else "baseline", args.family
        )
        for s, r in proof["coins"].items()
    }
    changed = [s for s in base.symbols if effective[s] != base_profiles[s]]
    proof["accepted_coins"] = changed
    digest = hashlib.sha256(
        json.dumps({s: asdict(p) for s, p in effective.items()}, sort_keys=True).encode()
    ).hexdigest()[:12]
    candidate = replace(
        base,
        version="HIXTON-V8-COIN-DD-RESEARCH-" + digest,
        paper_approved=False,
        coin_profiles=tuple(effective[s] for s in base.symbols),
    )
    proof["candidate_version"] = candidate.version
    for label, start in (("full", START), ("validation", START.replace(year=2025))):
        proof["portfolio"][label] = {}
        for name, definition in (("baseline", base), ("candidate", candidate)):
            scenarios = {}
            for cost in (CURRENT_COSTS, STRESS_COSTS):
                r = run_shared_portfolio_backtest(
                    candles_by_symbol=history.candles_by_symbol,
                    report_start_utc=start,
                    report_end_utc=END,
                    starting_cash=SEED,
                    target_notional=SEED / 2,
                    slot_count=2,
                    costs=cost,
                    execution_rules=rules,
                    strategy=definition,
                    reinvest_profits=True,
                    autonomous_spot=True,
                )
                scenarios[cost.name] = r
                stats = summary(r)
                stats["trades_by_symbol"] = dict(Counter(t.symbol for t in r.trades))
                proof["portfolio"][label].setdefault(name, {})[cost.name] = stats
                print("PORTFOLIO", label, name, cost.name, stats, flush=True)
                save()
            report = write_report_bundle(
                scenarios=scenarios,
                output_root=args.out / "reports" / label / name,
                config_sha256=hashlib.sha256(
                    json.dumps(definition.config_payload(), sort_keys=True).encode()
                ).hexdigest(),
                code_commit="RESEARCH_SOURCE_IDENTIFIED_BY_SHA256_NO_PROMOTION",
                strategy=definition,
                report_start_utc=start,
                report_end_utc=END,
                history_data=continuity_manifest_data(history),
                trading_settings={
                    "slot_count": 2,
                    "auto_budget_enabled": True,
                    "autonomous_performance_enabled": True,
                    "capital_exposure_fraction": "1",
                },
                capital_source={
                    "kind": "DATED_SIMULATION_SEED_NO_PRIVATE_API_ACCESS",
                    "starting_usdc": str(SEED),
                },
            )
            proof["portfolio"][label][name]["report"] = str(report)
    # A weak coin does not become deployable merely by improving its own account.
    checks = {}
    for label, rows in proof["portfolio"].items():
        for cost in ("current", "stress"):
            r, b = rows["candidate"][cost], rows["baseline"][cost]
            base_return = D(b["return_pct"])
            threshold = base_return * D(".80") if base_return > 0 else base_return
            checks[label + "_" + cost] = D(r["return_pct"]) >= threshold and D(r["dd_pct"]) <= D(
                b["dd_pct"]
            ) * (D(".80") if label == "full" else D("1"))
    proof["portfolio_acceptance_checks"] = checks
    proof["portfolio_candidate_passed"] = bool(changed) and all(checks.values())
    save()
    print(
        "DONE",
        "changed",
        changed,
        "portfolio accepted",
        proof["portfolio_candidate_passed"],
        flush=True,
    )


if __name__ == "__main__":
    main()

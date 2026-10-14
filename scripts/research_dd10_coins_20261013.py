"""Current DD10 per-coin research on a public, immutable market snapshot.

No network, credentials, exchange orders, runtime state or strategy installation.
The catalogue and temporal gates are serialized before any new experiment.
History was previously examined; the last year is not a pristine holdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime
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

CATALOGUE = (
    "baseline",
    "cmo55",
    "cmo65",
    "slope24",
    "slope72",
    "band90",
    "vidya_plus2",
    "stop8",
    "stop12",
    "trail16",
)
SELECTION = {
    "training": "Two chronological fresh-account years with stress costs. Each fold: >=3 "
    "completed trades, DD no worse, >=85% positive baseline return or no worse negative "
    "return. Summed return >=90% summed positive baseline returns. Worst-fold DD "
    "reduced >=5% relatively. Select lowest worst-fold DD, then highest summed return. "
    "Freeze one winner per coin before final-year or full-period candidate evaluation.",
    "coin_validation": "Full period at BOTH costs: no lower ending capital and strictly "
    "lower DD. Final year at BOTH costs: retain >=90% positive baseline return or do "
    "not worsen negative baseline return, and no higher DD. Do not substitute another "
    "candidate after validation failure.",
    "portfolio_validation": "Unchanged native current DD10 shared allocator. At BOTH "
    "costs: full ending capital improves >=1%, DD improves >=2% relatively. Fresh-account "
    "final-year return and DD must not worsen. Only validated coins currently eligible "
    "in the shared strategy are tested individually and together. No coin activation.",
    "limitations": "Previously examined history, adaptive research; no untouched "
    "out-of-sample claim, no future capital guarantee and no formal promotion.",
}


class SnapshotOnly:
    def fetch_klines(self, *args, **kwargs):
        raise RuntimeError("Snapshot incomplete: no network replacement allowed")


def summary(run):
    m = run.metrics
    return {
        "ending_usdc": str(m.ending_equity),
        "return_pct": str(m.return_pct),
        "dd_pct": str(m.max_drawdown_pct),
        "trades": m.completed_trades,
        "fees_usdc": str(m.total_fees),
        "profit_factor": str(m.profit_factor),
        "max_holding_hours": str(m.max_holding_hours),
        "open_at_end": getattr(
            run, "open_position_at_end", getattr(run, "open_symbols_at_end", None)
        ),
    }


def variant(profile, name):
    p, t = profile.parameters, profile.trade_policy
    if name == "baseline":
        return profile
    if name in ("cmo55", "cmo65"):
        t = replace(t, cmo_floor=max(t.cmo_floor, int(name[3:]) / 100))
    elif name in ("slope24", "slope72"):
        t = replace(t, slope_bars=max(t.slope_bars, int(name[5:])))
    elif name == "band90":
        p = replace(p, band_multiplier=round(p.band_multiplier * 0.9, 3))
    elif name == "vidya_plus2":
        p = replace(p, vidya_length=p.vidya_length + 2)
    elif name in ("stop8", "stop12"):
        # Do not loosen any existing XRP/AAVE/SUI protective stop.
        t = replace(t, stop_atr=t.stop_atr or int(name[4:]))
    elif name == "trail16":
        t = replace(t, trail_atr=min(t.trail_atr, 16) if t.trail_atr else 16)
    else:
        raise ValueError(name)
    return replace(profile, parameters=p, trade_policy=t)


def training_ok(rows, baseline):
    if not all(
        r["trades"] >= 3
        and D(r["dd_pct"]) <= D(b["dd_pct"])
        and D(r["return_pct"])
        >= (D(b["return_pct"]) * D(".85") if D(b["return_pct"]) > 0 else D(b["return_pct"]))
        for r, b in zip(rows, baseline, strict=True)
    ):
        return False
    return sum((D(r["return_pct"]) for r in rows), D(0)) >= sum(
        (max(D(0), D(b["return_pct"])) for b in baseline), D(0)
    ) * D(".90") and max(D(r["dd_pct"]) for r in rows) <= max(D(b["dd_pct"]) for b in baseline) * D(
        ".95"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    args = ap.parse_args()
    inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
    out = args.inputs.parent
    result_path = out / "Results.json"
    if result_path.exists():
        raise RuntimeError("Research results already exist; refuse to overwrite experiments")
    base = strategy_definition("v8r")
    assert base.version == inputs["base_strategy"]
    assert source_fingerprint() == inputs["source_sha256"]
    start, end = (datetime.fromisoformat(inputs[k]) for k in ("start", "end"))
    final_start = start.replace(year=2025)
    coin_seed, portfolio_seed = (D(inputs[k]) for k in ("coin_seed", "portfolio_seed"))
    data = Path(inputs["market_snapshot"])
    profiles = {p.symbol: p for p in base.coin_profiles}
    payload = {
        "status": "RUNNING_RESEARCH_ONLY",
        "installed": False,
        "orders_sent": False,
        "base_strategy": base.version,
        "source_sha256": source_fingerprint(),
        "research_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "period": [start.isoformat(), end.isoformat()],
        "coin_seed": str(coin_seed),
        "portfolio_seed": str(portfolio_seed),
        "catalogue": list(CATALOGUE),
        "selection": SELECTION,
        "costs": {c.name: asdict(c) for c in (CURRENT_COSTS, STRESS_COSTS)},
        "coins": {},
        "portfolio": {},
        "baseline_reproduced": False,
    }

    def save():
        result_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")

    save()  # Freeze catalogue and gates BEFORE ANY new experiment.
    rules = {}
    with CandleStore(data / "hixton-usdc.sqlite3", read_only=True) as store:
        for sym in base.symbols:
            r = store.load_symbol_rules(sym)
            if r is None:
                raise ValueError(sym)
            rules[sym] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
    history = load_continuity_history(
        strategy=base,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
        native_database_path=data / "hixton-usdc.sqlite3",
        cache_path=data / "backtest-history.sqlite3",
        client=SnapshotOnly(),
    )
    histdata = continuity_manifest_data(history)
    assert histdata["provenance_by_symbol"] == inputs["history_manifest"]["provenance_by_symbol"]
    payload["data"] = histdata

    def isolated(sym, p, s, e, cost):
        sat = SATELLITE_PROFILE_BY_SYMBOL.get(sym)
        # Satellite strategy parameters/policies are version-bound. Keep its
        # regime, macro-filter, horizon and all structural rules unchanged.
        if sat is not None:
            sat = replace(sat, parameters=p.parameters, trade_policy=p.trade_policy)
        return run_single_backtest(
            symbol=sym,
            candles=history.candles_by_symbol[sym],
            report_start_utc=s,
            report_end_utc=e,
            starting_cash=coin_seed,
            target_notional=coin_seed,
            costs=cost,
            execution_rules=rules[sym],
            strategy_parameters=p.parameters,
            trade_policy=p.trade_policy,
            strategy_semantics=base.semantics_for(sym),
            strategy_version=base.version,
            satellite_profile=sat,
            apply_risk_limits=True,
        )

    def definition(changes):
        if not changes:
            return base
        return replace(
            base,
            paper_approved=False,
            version="HIXTON-V8-DD10-COIN-RESEARCH-" + "-".join(sorted(changes)),
            coin_profiles=tuple(changes.get(p.symbol, p) for p in base.coin_profiles),
        )

    def shared(changes, s, e, cost):
        return run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=s,
            report_end_utc=e,
            starting_cash=portfolio_seed,
            target_notional=portfolio_seed / 2,
            costs=cost,
            execution_rules=rules,
            strategy=definition(changes),
            reinvest_profits=True,
            autonomous_spot=True,
        )

    def reports(label, scenarios, s, changes):
        strat = definition(changes)
        return str(
            write_report_bundle(
                scenarios=scenarios,
                output_root=out / "reports" / label,
                config_sha256=hashlib.sha256(
                    json.dumps(strat.config_payload(), sort_keys=True).encode()
                ).hexdigest(),
                code_commit="RESEARCH_NO_PROMOTION",
                report_start_utc=s,
                report_end_utc=end,
                strategy=strat,
                history_data=histdata,
                trading_settings={
                    "auto_budget_enabled": True,
                    "autonomous_performance_enabled": True,
                    "slot_count": 2,
                },
            )
        )

    # Reproduce all 15 unrounded isolated end values and DD, not just display rounding.
    for sym in base.symbols:
        run = isolated(sym, profiles[sym], start, end, CURRENT_COSTS)
        assert (
            run.data_snapshot_sha256 == inputs["history_manifest"]["snapshot_sha256_by_symbol"][sym]
        )
        m, expected = run.metrics, inputs["expected_coin_metrics"][sym]
        for field in ("ending_equity", "max_drawdown_pct", "total_fees"):
            assert getattr(m, field) == D(expected[field]), (
                sym,
                field,
                getattr(m, field),
                expected[field],
            )
        assert m.completed_trades == expected["completed_trades"]
        payload["coins"][sym] = {"baseline_full": {"current": summary(run)}}
        save()
        print("REPRODUCED", sym, summary(run), flush=True)
    run = shared({}, start, end, CURRENT_COSTS)
    for field in ("ending_equity", "max_drawdown_pct", "total_fees"):
        assert getattr(run.metrics, field) == D(inputs["expected_portfolio_metrics"][field]), field
    assert run.metrics.completed_trades == inputs["expected_portfolio_metrics"]["completed_trades"]
    payload["portfolio"]["baseline_full"] = {"current": summary(run)}
    payload["portfolio"]["current_coin_contributions"] = {
        sym: {
            "trades": sum(t.symbol == sym for t in run.trades),
            "realized_pnl_usdc": str(
                sum((t.realized_pnl for t in run.trades if t.symbol == sym), D(0))
            ),
            "worst_trade_return_pct": str(
                min((t.realized_return_pct for t in run.trades if t.symbol == sym), default=D(0))
            ),
        }
        for sym in base.symbols
    }
    # Native reports retain curves, fill times and completed trades for independent checks.
    payload["portfolio"]["baseline_current_report"] = reports(
        "baseline-reproduction", {"current": run}, start, {}
    )
    payload["baseline_reproduced"] = True
    save()
    print("REPRODUCED SHARED", summary(run), flush=True)
    # All training is completed before any candidate validation.
    frozen = {}
    for sym in base.symbols:
        row = payload["coins"][sym]
        row.update(train={}, profiles={})
        seen = set()
        for name in CATALOGUE:
            p = variant(profiles[sym], name)
            identity = (p.parameters, p.trade_policy)
            if identity in seen:
                continue
            seen.add(identity)
            row["profiles"][name] = asdict(p)
            row["train"][name] = [
                summary(
                    isolated(sym, p, start.replace(year=y), start.replace(year=y + 1), STRESS_COSTS)
                )
                for y in (2023, 2024)
            ]
        eligible = [
            n
            for n, rows in row["train"].items()
            if n != "baseline" and training_ok(rows, row["train"]["baseline"])
        ]
        winner = min(
            eligible,
            key=lambda n: (
                max(D(r["dd_pct"]) for r in row["train"][n]),
                -sum((D(r["return_pct"]) for r in row["train"][n]), D(0)),
            ),
            default=None,
        )
        row["training_eligible"] = eligible
        row["frozen_winner"] = winner
        frozen[sym] = winner
        save()
        print("TRAIN", sym, "eligible", eligible, "frozen", winner, flush=True)
    payload["frozen_selections"] = frozen
    save()
    selected = {}
    for sym, winner in frozen.items():
        if winner is None:
            continue
        row = payload["coins"][sym]
        profile = variant(profiles[sym], winner)
        row.update(candidate_full={}, baseline_final={}, candidate_final={}, validation_checks={})
        for cost in (CURRENT_COSTS, STRESS_COSTS):
            if cost.name != "current":
                row["baseline_full"][cost.name] = summary(
                    isolated(sym, profiles[sym], start, end, cost)
                )
            row["candidate_full"][cost.name] = summary(isolated(sym, profile, start, end, cost))
            row["baseline_final"][cost.name] = summary(
                isolated(sym, profiles[sym], final_start, end, cost)
            )
            row["candidate_final"][cost.name] = summary(
                isolated(sym, profile, final_start, end, cost)
            )
            r, b = row["candidate_full"][cost.name], row["baseline_full"][cost.name]
            row["validation_checks"]["full_" + cost.name] = D(r["ending_usdc"]) >= D(
                b["ending_usdc"]
            ) and D(r["dd_pct"]) < D(b["dd_pct"])
            r, b = row["candidate_final"][cost.name], row["baseline_final"][cost.name]
            threshold = (
                D(b["return_pct"]) * D(".90") if D(b["return_pct"]) > 0 else D(b["return_pct"])
            )
            row["validation_checks"]["final_" + cost.name] = D(r["return_pct"]) >= threshold and D(
                r["dd_pct"]
            ) <= D(b["dd_pct"])
        row["validated_improvement"] = all(row["validation_checks"].values())
        if row["validated_improvement"]:
            selected[sym] = profile
        save()
        print(
            "VALIDATED",
            sym,
            winner,
            row["validated_improvement"],
            "full",
            row["candidate_full"],
            "final_checks",
            row["validation_checks"],
            flush=True,
        )
    # Research-only SUI/UNI and performance-ineligible AAVE remain excluded.
    active = (set(base.symbols) - set(base.satellite_symbols)) | {"NEARUSDC", "BCHUSDC"}
    active_selected = {s: p for s, p in selected.items() if s in active}
    payload["validated_coins"] = list(selected)
    payload["active_validated_coins"] = list(active_selected)
    experiments = {s: {s: p} for s, p in active_selected.items()}
    if len(active_selected) > 1:
        experiments["combined"] = active_selected
    if experiments:
        for label, s in (("full", start), ("final", final_start)):
            scenarios = {c.name: shared({}, s, end, c) for c in (CURRENT_COSTS, STRESS_COSTS)}
            payload["portfolio"]["baseline_" + label] = {
                k: summary(v) for k, v in scenarios.items()
            }
            payload["portfolio"]["baseline_" + label + "_report"] = reports(
                "baseline-" + label, scenarios, s, {}
            )
            save()
            for name, changes in experiments.items():
                scenarios = {
                    c.name: shared(changes, s, end, c) for c in (CURRENT_COSTS, STRESS_COSTS)
                }
                row = payload["portfolio"].setdefault("candidates", {}).setdefault(name, {})
                row[label] = {k: summary(v) for k, v in scenarios.items()}
                row[label + "_report"] = reports(name + "-" + label, scenarios, s, changes)
                save()
                print("PORTFOLIO", name, label, row[label], flush=True)
        for _name, row in payload["portfolio"]["candidates"].items():
            checks = {}
            for cost in ("current", "stress"):
                r, b = row["full"][cost], payload["portfolio"]["baseline_full"][cost]
                checks["full_" + cost] = D(r["ending_usdc"]) >= D(b["ending_usdc"]) * D(
                    "1.01"
                ) and D(r["dd_pct"]) <= D(b["dd_pct"]) * D(".98")
                r, b = row["final"][cost], payload["portfolio"]["baseline_final"][cost]
                checks["final_" + cost] = D(r["return_pct"]) >= D(b["return_pct"]) and D(
                    r["dd_pct"]
                ) <= D(b["dd_pct"])
            row["checks"] = checks
            row["accepted_for_review"] = all(checks.values())
    payload["status"] = "COMPLETED_RESEARCH_ONLY"
    payload["runtime_source_still_matches"] = source_fingerprint() == inputs["source_sha256"]
    assert payload["runtime_source_still_matches"]
    save()
    print(
        "DONE",
        {
            "coin_improvements": list(selected),
            "active": list(active_selected),
            "portfolio_accepted": [
                n
                for n, r in payload["portfolio"].get("candidates", {}).items()
                if r["accepted_for_review"]
            ],
        },
        flush=True,
    )


if __name__ == "__main__":
    main()

"""Locate concentration-led drawdowns and test causal switches; no runtime changes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

from concentration_portfolio_20261013 import run_shared_portfolio_backtest as research_run
from concentration_research_support_20261013 import ConcentrationPolicy
from research_dd10_coins_20261013 import SnapshotOnly, summary

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest as native_run
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.models import SignalAction
from hixton.domain.versions import strategy_definition

CATALOGUE = {
    "baseline": None,
    "entry_only_4_20k": ConcentrationPolicy(D(20000), trim_on_activation=False),
    "switch_4_20k": ConcentrationPolicy(D(20000)),
    "switch_4_25k": ConcentrationPolicy(D(25000)),
    "switch_4_30k": ConcentrationPolicy(D(30000)),
    "dd3_4_20k": ConcentrationPolicy(D(20000), D(3)),
    "dd5_4_20k": ConcentrationPolicy(D(20000), D(5)),
    "dd3_4_30k": ConcentrationPolicy(D(30000), D(3)),
    "switch_6_30k": ConcentrationPolicy(D(30000), slots=6),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(exist_ok=True)
    if (args.out / "Results.json").exists() and not args.resume:
        raise RuntimeError("Do not overwrite a research experiment")
    i = json.loads(args.inputs.read_text(encoding="utf-8"))
    base = strategy_definition("v8r")
    start, end = (datetime.fromisoformat(i[k]) for k in ("start", "end"))
    seed = D(i["portfolio_seed"])
    original = json.loads((args.out / "Original-DD-Episoden.json").read_text(encoding="utf-8"))
    worst = original["largest_pct"][0]
    oracle_date = datetime.fromisoformat(worst["peak_utc"]) - timedelta(hours=24)
    payload = {
        "status": "RUNNING_RESEARCH_ONLY",
        "installed": False,
        "orders_sent": False,
        "base_strategy": base.version,
        "source_sha256": source_fingerprint(),
        "script_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in map(
                Path,
                (
                    "scripts/research_concentration_switch_20261013.py",
                    "scripts/concentration_portfolio_20261013.py",
                    "scripts/concentration_research_support_20261013.py",
                ),
            )
        },
        "catalogue": {n: asdict(v) if v else None for n, v in CATALOGUE.items()},
        "oracle": {
            "label": "RETROSPECTIVE_ONLY_NOT_CAUSAL_NOT_ELIGIBLE",
            "switch_date": oracle_date.isoformat(),
            "why": (
                "Exactly 24h before the known worst historical peak. Future peak used onl"
                "y for this explicitly labeled diagnostic."
            ),
        },
        "period": [start.isoformat(), end.isoformat()],
        "seed": str(seed),
        "full": {},
        "last_year_probe": {},
        "method": (
            "All catalogue rules frozen before new runs. Mode latches after previous "
            "closed equity reaches threshold; DD rules also need previous DD. Only on"
            "e trim at activation, priced next open; regular same-open exits skip ext"
            "ra trim. Existing small positions get new capacity without artificial ca"
            "sh. New entries keep fresh flip signals, ATR075, fees, rounding, Core pr"
            "iority and daily pause. One position per coin, cap 25% or 1/6 before ATR"
            ". No weak/new/research-only coin activation. If signals unavailable cash"
            " remains cash. Partial trim lots are not counted as fully closed positio"
            "n cycles."
        ),
        "limits": (
            "Previously examined history; this is adaptive research, not an untouched"
            " holdout or Live/Paper approval. Full/final evaluations report every fix"
            "ed causal candidate, no automatic winner installation. Oracle never ente"
            "rs causal comparisons."
        ),
    }

    if args.resume:
        saved = json.loads((args.out / "Results.json").read_text(encoding="utf-8"))
        assert saved["source_sha256"] == payload["source_sha256"]
        assert saved["catalogue"] == json.loads(json.dumps(payload["catalogue"], default=str))
        assert saved["period"] == payload["period"]
        saved["metadata_repair"] = {
            "original_script_hashes": saved["script_hashes"],
            "repaired_script_hashes": payload["script_hashes"],
            "scope": (
                "Decimal serialization in report metadata; baseline and all existing "
                "numerical results preserved, no policy/gate changes"
            ),
        }
        payload = saved

    def save():
        (args.out / "Results.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )

    save()
    rules = {}
    data = Path(i["market_snapshot"])
    with CandleStore(data / "hixton-usdc.sqlite3", read_only=True) as store:
        for sym in base.symbols:
            r = store.load_symbol_rules(sym)
            assert r
            rules[sym] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
    h = load_continuity_history(
        strategy=base,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
        native_database_path=data / "hixton-usdc.sqlite3",
        cache_path=data / "backtest-history.sqlite3",
        client=SnapshotOnly(),
    )
    hdata = continuity_manifest_data(h)
    payload["data"] = hdata

    def kwargs(s, c, cash):
        return {
            "candles_by_symbol": h.candles_by_symbol,
            "report_start_utc": s,
            "report_end_utc": end,
            "starting_cash": cash,
            "target_notional": cash / 2,
            "costs": c,
            "execution_rules": rules,
            "strategy": base,
            "reinvest_profits": True,
            "autonomous_spot": True,
        }

    def run(name, policy, s, c, cash, label):
        audit = []
        r = research_run(**kwargs(s, c, cash), research_policy=policy, research_audit=audit)
        events = [e for row in audit for e in row["events"]]
        trims = [e for e in events if e["kind"] == "PARTIAL_TRIM"]
        trim_ids = {e["signal_id"] for e in trims}
        row = summary(r)
        row.update(
            partial_trim_count=len(trims),
            completed_position_cycles=sum(t.exit_signal_id not in trim_ids for t in r.trades),
            max_distinct_coins=max(len(x["positions"]) for x in audit),
            mean_cash_pct=str(
                sum((D(x["cash"]) / D(x["equity"]) * 100 for x in audit), D(0)) / D(len(audit))
            ),
            max_single_coin_pct=str(
                max(
                    (
                        max(
                            (D(p["value"]) / D(x["equity"]) * 100 for p in x["positions"].values()),
                            default=D(0),
                        )
                        for x in audit
                    ),
                    default=D(0),
                )
            ),
            switch_events=[e for e in events if e["kind"] == "SWITCH"],
            trim_events=trims,
        )
        # Ledger arithmetic and ownership: mark agrees with native equity point,
        # quantities stay positive, cash never reused, max distinct limit respected.
        assert all(
            D(x["cash"]) >= 0 and all(D(p["quantity"]) > 0 for p in x["positions"].values())
            for x in audit
        )
        assert all(
            D(x["equity"]) == ep.equity and D(x["cash"]) == ep.cash
            for x, ep in zip(audit, r.equity_curve, strict=True)
        )
        if policy:
            assert all(len(x["positions"]) <= max(3, policy.slots) for x in audit)
            for e in events:
                assert datetime.fromisoformat(e["decision_close"]) < datetime.fromisoformat(
                    e["execution_open"]
                )
        with gzip.open(
            args.out / f"{label}-{name}-{c.name}-ledger.jsonl.gz", "wt", encoding="utf-8"
        ) as f:
            for x in audit:
                f.write(json.dumps(x) + "\n")
        print(
            "RUN",
            label,
            name,
            c.name,
            "end",
            row["ending_usdc"],
            "DD",
            row["dd_pct"],
            "coins",
            row["max_distinct_coins"],
            "trims",
            len(trims),
            flush=True,
        )
        return r, audit, row

    # BOTH normal and stress disabled copies exactly equal native curve, fills,
    # trades and metrics before trusting any intervention outcome.
    for c in (CURRENT_COSTS, STRESS_COSTS):
        if (
            args.resume
            and payload.get("disabled_copy_matches_native")
            and c.name in payload["full"].get("baseline", {})
        ):
            continue
        prod = native_run(**kwargs(start, c, seed))
        r, audit, row = run("baseline", None, start, c, seed, "full")
        assert (
            prod.equity_curve == r.equity_curve
            and prod.fills == r.fills
            and prod.trades == r.trades
            and prod.metrics == r.metrics
        )
        expected_path = (
            args.inputs.parent.parent / "ETH8-Weitere-Forschung-20261013" / "Results.json"
        )
        expected = json.loads(expected_path.read_text(encoding="utf-8"))["validation"]["full"][
            "baseline"
        ][c.name]
        assert json.loads(json.dumps(summary(r))) == {
            k: v for k, v in expected.items() if k != "report"
        }
        payload["full"].setdefault("baseline", {})[c.name] = row
        payload["disabled_copy_matches_native"] = True
        if c.name == "current":
            # Exact symbol PnL attribution over the ORIGINAL drawdown windows.
            bytime = {x["time"]: x for x in audit}
            signal_symbols = {x.signal_id: x.symbol for x in r.signals}
            prices = {
                s: {b.close_time_utc.isoformat(): D(str(b.close)) for b in bars}
                for s, bars in h.candles_by_symbol.items()
            }
            episodes = []
            for ep in original["largest_pct"]:
                pt, tt = ep["peak_utc"], ep["trough_utc"]
                peak, trough = bytime[pt], bytime[tt]
                cash_changes = dict.fromkeys(base.symbols, D(0))
                for fill in r.fills:
                    at = fill.fill_time_utc.isoformat()
                    if pt < at <= tt:
                        sym = signal_symbols[fill.signal_id]
                        cash_changes[sym] += (
                            fill.quote_value - fill.fee_quote_equivalent
                            if fill.action is SignalAction.EXIT_LONG
                            else -fill.quote_value
                        )
                # Remaining dust is tiny but must be attributed, not silently zeroed.
                dict.fromkeys(base.symbols, D(0))

                def values_at(
                    time, candidate_run=r, sym_lookup=signal_symbols, price_lookup=prices
                ):
                    quantities = dict.fromkeys(base.symbols, D(0))
                    for f in candidate_run.fills:
                        if f.fill_time_utc.isoformat() <= time:
                            sym = sym_lookup[f.signal_id]
                            quantities[sym] += (
                                f.base_quantity
                                if f.action is SignalAction.ENTER_LONG
                                else -f.base_quantity
                            )
                    return {s: quantities[s] * price_lookup[s][time] for s in base.symbols}

                pv, tv = values_at(pt), values_at(tt)
                contributions = {s: tv[s] - pv[s] + cash_changes[s] for s in base.symbols}
                assert abs(
                    sum(contributions.values(), D(0)) - (D(trough["equity"]) - D(peak["equity"]))
                ) < D("1e-16")
                episodes.append(
                    {
                        "original_episode": ep,
                        "peak_positions": peak["positions"],
                        "peak_cash": peak["cash"],
                        "trough_positions": trough["positions"],
                        "trough_cash": trough["cash"],
                        "contribution_by_symbol": {s: str(v) for s, v in contributions.items()},
                        "asset_close_return_pct": {
                            s: str((prices[s][tt] / prices[s][pt] - 1) * 100) for s in base.symbols
                        },
                        "fresh_eligible_signals_at_peak": peak["eligible_entries"],
                    }
                )
            payload["drawdown_attribution"] = episodes
        save()
    for name, policy in CATALOGUE.items():
        if name == "baseline":
            continue
        scenarios = {}
        payload["full"][name] = {}
        for c in (CURRENT_COSTS, STRESS_COSTS):
            r, _, row = run(name, policy, start, c, seed, "full")
            scenarios[c.name] = r
            payload["full"][name][c.name] = row
            save()
        payload["full"][name]["report"] = str(
            write_report_bundle(
                scenarios=scenarios,
                output_root=args.out / "reports" / "full" / name,
                config_sha256=hashlib.sha256(
                    json.dumps(asdict(policy), sort_keys=True, default=str).encode()
                ).hexdigest(),
                code_commit="RESEARCH_CONCENTRATION_NO_PROMOTION",
                report_start_utc=start,
                report_end_utc=end,
                strategy=base,
                history_data=hdata,
                trading_settings={
                    "auto_budget_enabled": True,
                    "autonomous_performance_enabled": True,
                    "research_concentration": json.loads(json.dumps(asdict(policy), default=str)),
                    "partial_lots_not_full_cycles": True,
                },
            )
        )
        save()
    # Explicit future-informed diagnostic; it can NEVER be proposed as a rule.
    policy = ConcentrationPolicy(D(0), oracle_start=oracle_date)
    payload["oracle"]["results"] = {}
    for c in (CURRENT_COSTS, STRESS_COSTS):
        _, _, row = run("ORACLE_PEAK_MINUS24H", policy, start, c, seed, "diagnostic")
        payload["oracle"]["results"][c.name] = row
        save()
    # Independent fresh 30k-account last-year probes EXERCISE every threshold.
    # All budget-only quarter switches are identical with a flat 30k start;
    # explicitly compare one representative, not duplicate the same run.
    last = {
        "baseline": None,
        "budget_quarters": ConcentrationPolicy(D(20000)),
        "dd3_quarters": ConcentrationPolicy(D(20000), D(3)),
        "dd5_quarters": ConcentrationPolicy(D(20000), D(5)),
        "budget_sixths": ConcentrationPolicy(D(30000), slots=6),
    }
    payload["last_year_probe_seed"] = "30000"
    payload["last_year_equivalence_groups"] = {
        "budget_quarters": ["entry_only_4_20k", "switch_4_20k", "switch_4_25k", "switch_4_30k"],
        "dd3_quarters": ["dd3_4_20k", "dd3_4_30k"],
        "dd5_quarters": ["dd5_4_20k"],
        "budget_sixths": ["switch_6_30k"],
    }
    # DD+30k cannot be grouped after falling below 30k: keep its actual threshold!
    last["dd3_30k_quarters"] = ConcentrationPolicy(D(30000), D(3))
    payload["last_year_equivalence_groups"]["dd3_quarters"] = ["dd3_4_20k"]
    payload["last_year_equivalence_groups"]["dd3_30k_quarters"] = ["dd3_4_30k"]
    for name, policy in last.items():
        payload["last_year_probe"][name] = {}
        for c in (CURRENT_COSTS, STRESS_COSTS):
            _, _, row = run(name, policy, start.replace(year=2025), c, D(30000), "last-year")
            payload["last_year_probe"][name][c.name] = row
            save()
    checks = {}
    b = payload["full"]["baseline"]
    for name in CATALOGUE:
        if name == "baseline":
            continue
        r = payload["full"][name]
        group = next(
            g for g, names in payload["last_year_equivalence_groups"].items() if name in names
        )
        last_rows = payload["last_year_probe"][group]
        lb = payload["last_year_probe"]["baseline"]
        checks[name] = {}
        for c in ("current", "stress"):
            checks[name]["full_" + c] = D(r[c]["ending_usdc"]) >= D(b[c]["ending_usdc"]) and D(
                r[c]["dd_pct"]
            ) < D(b[c]["dd_pct"])
            checks[name]["last_year_" + c] = D(last_rows[c]["return_pct"]) >= D(
                lb[c]["return_pct"]
            ) and D(last_rows[c]["dd_pct"]) <= D(lb[c]["dd_pct"])
        checks[name]["candidate_for_further_review"] = all(checks[name].values())
    payload["causal_checks"] = checks
    payload["status"] = "COMPLETED_RESEARCH_ONLY"
    assert source_fingerprint() == payload["source_sha256"]
    save()
    print("DONE", checks, flush=True)


if __name__ == "__main__":
    main()

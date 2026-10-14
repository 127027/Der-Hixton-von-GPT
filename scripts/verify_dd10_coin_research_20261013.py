"""Supplemental rejected AVAX diagnostic and independent report audits.

AVAX trail16 failed the frozen aggregate training-profit gate. It is explored
only to explain the losing isolated row, never substituted into the selection.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

from research_dd10_coins_20261013 import SnapshotOnly, summary, variant

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

ROOT = Path(
    r"C:\Users\andre\OneDrive\Desktop\Neuer Ordner\Pruefergebnisse\Coin-Nachoptimierung-20261013"
)
i = json.loads((ROOT / "Inputs.json").read_text(encoding="utf-8"))
r = json.loads((ROOT / "Results.json").read_text(encoding="utf-8"))
assert r["status"] == "COMPLETED_RESEARCH_ONLY"
payload = {
    "status": "EXPLORATORY_REJECTED_TRAINING_CANDIDATE",
    "installed": False,
    "orders_sent": False,
    "catalogue": ["AVAXUSDC:trail16"],
    "why": "AVAX is the only losing isolated coin; trail16 reduced training losses and DD "
    "but narrowly failed the predeclared summed-profit gate. "
    "This follow-up cannot convert it into an accepted candidate.",
    "accepted_for_review": False,
    "training_gate_failed": True,
    "runs": {},
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
assert i["source_sha256"] == source_fingerprint()
(ROOT / "AVAX-Exploration.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
base = strategy_definition("v8r")
start, end = (datetime.fromisoformat(i[k]) for k in ("start", "end"))
final = start.replace(year=2025)
snapshot = Path(i["market_snapshot"])
rules = {}
with CandleStore(snapshot / "hixton-usdc.sqlite3", read_only=True) as store:
    for sym in base.symbols:
        f = store.load_symbol_rules(sym)
        rules[sym] = ExecutionRules(f.tick_size, f.step_size, f.min_qty, f.min_notional)
h = load_continuity_history(
    strategy=base,
    report_start_utc=start,
    report_end_utc=end,
    execution_rules=rules,
    native_database_path=snapshot / "hixton-usdc.sqlite3",
    cache_path=snapshot / "backtest-history.sqlite3",
    client=SnapshotOnly(),
)
profiles = {p.symbol: p for p in base.coin_profiles}


def single(sym, p, s, c):
    return run_single_backtest(
        symbol=sym,
        candles=h.candles_by_symbol[sym],
        report_start_utc=s,
        report_end_utc=end,
        starting_cash=D(i["coin_seed"]),
        target_notional=D(i["coin_seed"]),
        costs=c,
        execution_rules=rules[sym],
        strategy_parameters=p.parameters,
        trade_policy=p.trade_policy,
        strategy_semantics=base.semantics_for(sym),
        strategy_version=base.version,
        apply_risk_limits=True,
    )


def report(label, runs, s, definition):
    return str(
        write_report_bundle(
            scenarios=runs,
            output_root=ROOT / "reports" / label,
            config_sha256=hashlib.sha256(
                json.dumps(definition.config_payload(), sort_keys=True).encode()
            ).hexdigest(),
            code_commit="RESEARCH_NO_PROMOTION",
            report_start_utc=s,
            report_end_utc=end,
            strategy=definition,
            history_data=continuity_manifest_data(h),
            trading_settings={"auto_budget_enabled": True, "autonomous_performance_enabled": True},
        )
    )


def definition(sym, name):
    p = variant(profiles[sym], name)
    return replace(
        base,
        version="HIXTON-V8-DD10-EXPLORATION-" + sym + "-" + name,
        paper_approved=False,
        coin_profiles=tuple(p if x.symbol == sym else x for x in base.coin_profiles),
    )


# Native isolated curves for the two validated single-coin candidates.
iso_reports = {}
for sym in ("ETHUSDC", "DOGEUSDC"):
    winner = r["coins"][sym]["frozen_winner"]
    iso_reports[sym] = {}
    for name in ("baseline", winner):
        run = single(sym, variant(profiles[sym], name), start, CURRENT_COSTS)
        expected = r["coins"][sym]["baseline_full" if name == "baseline" else "candidate_full"][
            "current"
        ]
        assert summary(run) == expected
        iso_reports[sym][name] = report(
            "isolated-" + sym + "-" + name,
            {"current": run},
            start,
            base if name == "baseline" else definition(sym, name),
        )
        print("ISOLATED CURVE VERIFIED", sym, name, flush=True)
(ROOT / "Isolated-Candidate-Reports.json").write_text(
    json.dumps(iso_reports, indent=2), encoding="utf-8"
)
# Frozen exploratory AVAX only. Does not overwrite main experiment selections.
sym = "AVAXUSDC"
p = variant(profiles[sym], "trail16")
strat = definition(sym, "trail16")
for label, s in (("full", start), ("final", final)):
    row = {}
    for cost in (CURRENT_COSTS, STRESS_COSTS):
        b = single(sym, profiles[sym], s, cost)
        c = single(sym, p, s, cost)
        row[cost.name] = {"baseline": summary(b), "candidate": summary(c)}
    payload["runs"]["isolated_" + label] = row
    (ROOT / "AVAX-Exploration.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("AVAX ISOLATED", label, row, flush=True)
    runs = {
        cost.name: run_shared_portfolio_backtest(
            candles_by_symbol=h.candles_by_symbol,
            report_start_utc=s,
            report_end_utc=end,
            starting_cash=D(i["portfolio_seed"]),
            target_notional=D(i["portfolio_seed"]) / 2,
            costs=cost,
            execution_rules=rules,
            strategy=strat,
            reinvest_profits=True,
            autonomous_spot=True,
        )
        for cost in (CURRENT_COSTS, STRESS_COSTS)
    }
    payload["runs"]["shared_" + label] = {k: summary(v) for k, v in runs.items()}
    payload["runs"]["shared_" + label + "_report"] = report(
        "rejected-AVAX-" + label, runs, s, strat
    )
    (ROOT / "AVAX-Exploration.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("AVAX SHARED", label, payload["runs"]["shared_" + label], flush=True)

# Recompute every shared and isolated saved research report from CSV independently.
verified = []
for mf in (ROOT / "reports").rglob("manifest.json"):
    folder = mf.parent
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
    curves = {}
    counts = {}
    with (folder / "equity.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["scenario"], row["symbol"])
            curves.setdefault(key, []).append(D(row["equity"]))
    with (folder / "trades.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["scenario"], row["symbol"])
            counts[key] = counts.get(key, 0) + 1
    for (scenario, symbol), curve in curves.items():
        m = metrics[scenario].get("portfolio", {}).get("metrics")
        if m is None:
            m = metrics[scenario]["per_symbol"][symbol]
        assert curve[-1] == D(m["ending_equity"])
        peak = D(m["starting_equity"])
        dd = D(0)
        for e in curve:
            peak = max(peak, e)
            dd = max(dd, (peak - e) / peak * 100)
        assert abs(dd - D(m["max_drawdown_pct"])) < D("0.000000001")
        actual_count = (
            sum(n for (s, y), n in counts.items() if s == scenario)
            if "portfolio" in metrics[scenario]
            else counts.get((scenario, symbol), 0)
        )
        assert actual_count == m["completed_trades"]
        verified.append(
            {
                "report": str(folder),
                "scenario": scenario,
                "symbol": symbol,
                "ending_usdc": str(curve[-1]),
                "dd_pct": str(dd),
                "trades": actual_count,
            }
        )
(ROOT / "Research-CSV-Verification.json").write_text(
    json.dumps({"all_passed": True, "rows": verified}, indent=2), encoding="utf-8"
)
payload["status"] = "COMPLETED_EXPLORATORY_REJECTED_TRAINING_CANDIDATE"
payload["source_unchanged"] = source_fingerprint() == i["source_sha256"]
assert payload["source_unchanged"]
(ROOT / "AVAX-Exploration.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("INDEPENDENT CSV CHECKS PASS", len(verified), flush=True)

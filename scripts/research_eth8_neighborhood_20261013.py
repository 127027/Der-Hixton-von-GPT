"""Small native shared-portfolio neighborhood after owner-selected ETH stop8.

Public immutable snapshot only. Fresh-year stress training, frozen selection,
then full/final-year comparisons. Previously examined history is not an unseen
holdout. No runtime modification, private account access or orders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

from research_dd10_coins_20261013 import SnapshotOnly, summary

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

CATALOGUE = {
    "baseline": None,
    "eth_stop6": ("ETHUSDC", "stop_atr", 6),
    "eth_stop10": ("ETHUSDC", "stop_atr", 10),
    "eth_stop12": ("ETHUSDC", "stop_atr", 12),
    "doge_cmo45": ("DOGEUSDC", "cmo_floor", 0.45),
    "doge_cmo55": ("DOGEUSDC", "cmo_floor", 0.55),
    "xrp_cmo20": ("XRPUSDC", "cmo_floor", 0.20),
    "xrp_cmo25": ("XRPUSDC", "cmo_floor", 0.25),
    "avax_cmo10": ("AVAXUSDC", "cmo_floor", 0.10),
    "avax_cmo20": ("AVAXUSDC", "cmo_floor", 0.20),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    i = json.loads(args.inputs.read_text(encoding="utf-8"))
    base = strategy_definition("v8r")
    assert base.policy_for("ETHUSDC").stop_atr == 8
    start, end = (datetime.fromisoformat(i[k]) for k in ("start", "end"))
    final_start = start.replace(year=2025)
    seed = D(i["portfolio_seed"])
    data = Path(i["market_snapshot"])
    payload = {
        "status": "RUNNING_RESEARCH_ONLY",
        "installed": False,
        "orders_sent": False,
        "base_strategy": base.version,
        "source_sha256": source_fingerprint(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "period": [start.isoformat(), end.isoformat()],
        "seed": str(seed),
        "catalogue": CATALOGUE,
        "costs": {c.name: asdict(c) for c in (CURRENT_COSTS, STRESS_COSTS)},
        "selection": "Two chronological fresh-account stress-cost training folds: each fold "
        ">=10 trades, DD no higher, >=95% positive baseline return or no worse negative "
        "return; worst-fold DD at least 2% lower relatively. Rank highest minimum fold "
        "return/DD ratio, then summed return. Freeze one winner before full/final-year "
        "runs. Full BOTH costs: ending capital >=101% baseline and DD <=98% baseline. "
        "Fresh final year BOTH costs: return and DD no worse. No replacement winner "
        "after failure; no adoption, news input, allocator change or risk-gate weakening.",
        "limitations": "Adaptive neighborhood on previously examined history, no pristine "
        "holdout and no future profitability guarantee.",
        "train": {},
        "validation": {},
    }

    def save():
        (args.out / "Results.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )

    save()
    rules = {}
    with CandleStore(data / "hixton-usdc.sqlite3", read_only=True) as store:
        for sym in base.symbols:
            r = store.load_symbol_rules(sym)
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
    hdata = continuity_manifest_data(history)
    payload["data"] = hdata

    def definition(name):
        change = CATALOGUE[name]
        if change is None:
            return base
        sym, field, value = change
        return replace(
            base,
            paper_approved=False,
            version="HIXTON-V8-ETH8-NEIGHBORHOOD-RESEARCH-" + name,
            coin_profiles=tuple(
                replace(p, trade_policy=replace(p.trade_policy, **{field: value}))
                if p.symbol == sym
                else p
                for p in base.coin_profiles
            ),
        )

    def run(name, s, e, cost):
        return run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=s,
            report_end_utc=e,
            starting_cash=seed,
            target_notional=seed / 2,
            execution_rules=rules,
            strategy=definition(name),
            costs=cost,
            reinvest_profits=True,
            autonomous_spot=True,
        )

    for name in CATALOGUE:
        payload["train"][name] = [
            summary(run(name, start.replace(year=y), start.replace(year=y + 1), STRESS_COSTS))
            for y in (2023, 2024)
        ]
        save()
        print("TRAIN", name, payload["train"][name], flush=True)
    baseline = payload["train"]["baseline"]
    eligible = [
        name
        for name, rows in payload["train"].items()
        if name != "baseline"
        and all(
            r["trades"] >= 10
            and D(r["dd_pct"]) <= D(b["dd_pct"])
            and D(r["return_pct"])
            >= (D(b["return_pct"]) * D(".95") if D(b["return_pct"]) > 0 else D(b["return_pct"]))
            for r, b in zip(rows, baseline, strict=True)
        )
        and max(D(r["dd_pct"]) for r in rows) <= max(D(b["dd_pct"]) for b in baseline) * D(".98")
    ]
    winner = max(
        eligible,
        key=lambda n: (
            min(D(r["return_pct"]) / max(D(r["dd_pct"]), D(".01")) for r in payload["train"][n]),
            sum((D(r["return_pct"]) for r in payload["train"][n]), D(0)),
        ),
        default=None,
    )
    payload["training_eligible"] = eligible
    payload["frozen_winner"] = winner
    save()
    print("FROZEN", winner, eligible, flush=True)
    # Baseline and winner only; rejected candidates are not rescored on later data.
    for label, s in (("full", start), ("final", final_start)):
        payload["validation"][label] = {}
        for name in ("baseline", winner) if winner else ("baseline",):
            runs = {c.name: run(name, s, end, c) for c in (CURRENT_COSTS, STRESS_COSTS)}
            row = {k: summary(v) for k, v in runs.items()}
            row["report"] = str(
                write_report_bundle(
                    scenarios=runs,
                    output_root=args.out / "reports" / label / name,
                    config_sha256=hashlib.sha256(
                        json.dumps(definition(name).config_payload(), sort_keys=True).encode()
                    ).hexdigest(),
                    code_commit="RESEARCH_NO_PROMOTION",
                    report_start_utc=s,
                    report_end_utc=end,
                    strategy=definition(name),
                    history_data=hdata,
                    trading_settings={
                        "auto_budget_enabled": True,
                        "autonomous_performance_enabled": True,
                        "slot_count": 2,
                    },
                )
            )
            payload["validation"][label][name] = row
            save()
            print("VALIDATION", label, name, row, flush=True)
    checks = {}
    if winner:
        for cost in ("current", "stress"):
            r, b = (payload["validation"]["full"][n][cost] for n in (winner, "baseline"))
            checks["full_" + cost] = D(r["ending_usdc"]) >= D(b["ending_usdc"]) * D("1.01") and D(
                r["dd_pct"]
            ) <= D(b["dd_pct"]) * D(".98")
            r, b = (payload["validation"]["final"][n][cost] for n in (winner, "baseline"))
            checks["final_" + cost] = D(r["return_pct"]) >= D(b["return_pct"]) and D(
                r["dd_pct"]
            ) <= D(b["dd_pct"])
    payload["checks"] = checks
    payload["accepted_for_review"] = bool(winner) and all(checks.values())
    payload["status"] = "COMPLETED_RESEARCH_ONLY"
    assert source_fingerprint() == payload["source_sha256"]
    save()
    print("DONE", winner, payload["accepted_for_review"], flush=True)


if __name__ == "__main__":
    main()

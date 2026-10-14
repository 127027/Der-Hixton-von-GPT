"""Explicitly future-informed SIX-coin switch, diagnostic only, not eligible."""

import gzip
import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

from concentration_portfolio_20261013 import run_shared_portfolio_backtest
from concentration_research_support_20261013 import ConcentrationPolicy
from research_dd10_coins_20261013 import SnapshotOnly, summary

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

root = Path(
    r"C:\Users\andre\OneDrive\Desktop\Neuer Ordner\Pruefergebnisse\Konzentration-DD-Switch-20261013"
)
out = root / "Oracle6"
out.mkdir(exist_ok=True)
assert not (out / "Results.json").exists()
d = json.loads((root / "Results.json").read_text(encoding="utf-8"))
i = json.loads(
    (root.parent / "Coin-Nachoptimierung-20261013" / "Inputs.json").read_text(encoding="utf-8")
)
policy = ConcentrationPolicy(
    D(0), slots=6, oracle_start=datetime.fromisoformat(d["oracle"]["switch_date"])
)
payload = {
    "scope": "RETROSPECTIVE_ONLY_NOT_CAUSAL_NOT_ELIGIBLE",
    "policy": asdict(policy),
    "source": source_fingerprint(),
    "script_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "uses_known_future_peak_for_date": True,
    "installed": False,
    "accepted": False,
    "results": {},
}
(out / "Results.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
base = strategy_definition("v8r")
assert source_fingerprint() == d["source_sha256"]
start, end = (datetime.fromisoformat(i[k]) for k in ("start", "end"))
seed = D(i["portfolio_seed"])
data = Path(i["market_snapshot"])
rules = {}
with CandleStore(data / "hixton-usdc.sqlite3", read_only=True) as s:
    for sym in base.symbols:
        r = s.load_symbol_rules(sym)
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
runs = {}
for cost in (CURRENT_COSTS, STRESS_COSTS):
    audit = []
    run = run_shared_portfolio_backtest(
        candles_by_symbol=h.candles_by_symbol,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=seed,
        target_notional=seed / 2,
        costs=cost,
        execution_rules=rules,
        strategy=base,
        reinvest_profits=True,
        autonomous_spot=True,
        research_policy=policy,
        research_audit=audit,
    )
    assert all(D(x["cash"]) >= 0 and len(x["positions"]) <= 6 for x in audit)
    row = summary(run)
    row["max_distinct_coins"] = max(len(x["positions"]) for x in audit)
    row["events"] = [e for x in audit for e in x["events"]]
    assert all(
        datetime.fromisoformat(e["decision_close"]) < datetime.fromisoformat(e["execution_open"])
        for e in row["events"]
    )
    with gzip.open(out / (cost.name + "-ledger.jsonl.gz"), "wt", encoding="utf-8") as f:
        for x in audit:
            f.write(json.dumps(x) + "\n")
    peak = seed
    dd = D(0)
    for x in audit:
        e = D(x["equity"])
        peak = max(peak, e)
        dd = max(dd, (peak - e) / peak * 100)
    assert (
        abs(dd - run.metrics.max_drawdown_pct) < D("1e-9")
        and D(audit[-1]["equity"]) == run.metrics.ending_equity
    )
    payload["results"][cost.name] = row
    runs[cost.name] = run
    (out / "Results.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        "ORACLE6",
        cost.name,
        row["ending_usdc"],
        row["dd_pct"],
        row["max_distinct_coins"],
        flush=True,
    )
folder = write_report_bundle(
    scenarios=runs,
    output_root=out / "reports",
    config_sha256=hashlib.sha256(
        json.dumps(asdict(policy), sort_keys=True, default=str).encode()
    ).hexdigest(),
    code_commit="RETROSPECTIVE_DIAGNOSTIC_ONLY_NOT_ELIGIBLE",
    report_start_utc=start,
    report_end_utc=end,
    strategy=base,
    history_data=continuity_manifest_data(h),
    trading_settings={
        "research_overlay": json.loads(json.dumps(asdict(policy), default=str)),
        "scope": payload["scope"],
        "future_informed_date": True,
    },
)
(folder / "Research-Contract.json").write_text(
    json.dumps(
        {
            "scope": payload["scope"],
            "policy": json.loads(json.dumps(asdict(policy), default=str)),
            "installed": False,
            "product_or_live_approval": False,
        },
        indent=2,
    ),
    encoding="utf-8",
)
payload["report"] = str(folder)
payload["independent_equity_and_drawdown_passed"] = True
(out / "Results.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

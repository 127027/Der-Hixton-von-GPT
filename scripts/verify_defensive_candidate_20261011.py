"""Verify the registered candidate against the previously selected experiment."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition

a = argparse.ArgumentParser()
a.add_argument("--data", required=True)
args = a.parse_args()
data = Path(args.data)
strategy = strategy_definition("v8d")
seed = D("1092.05773944")
start = datetime(2023, 10, 11, 15, tzinfo=UTC)
end = datetime(2026, 10, 11, 15, tzinfo=UTC)
rules = {}
with CandleStore(data / "hixton-usdc.sqlite3", read_only=True) as store:
    for s in strategy.symbols:
        r = store.load_symbol_rules(s)
        rules[s] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
history = load_continuity_history(
    strategy=strategy,
    report_start_utc=start,
    report_end_utc=end,
    execution_rules=rules,
    native_database_path=data / "hixton-usdc.sqlite3",
    cache_path=data / "backtest-history.sqlite3",
)
expected = json.loads((data / "exposure-results.json").read_text())
proof = {
    "strategy": strategy.version,
    "python_source_sha256": source_fingerprint(),
    "results": {},
    "paper_approved": False,
    "installed": False,
}
for label, s in [("full", start), ("validation", start.replace(year=2025))]:
    scenarios = {}
    for costs in (CURRENT_COSTS, STRESS_COSTS):
        run = run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            report_start_utc=s,
            report_end_utc=end,
            starting_cash=seed,
            target_notional=seed / 2,
            slot_count=2,
            execution_rules=rules,
            strategy=strategy,
            costs=costs,
            reinvest_profits=True,
            autonomous_spot=True,
        )
        prior = expected[label]["exposure35"][costs.name]
        assert abs(run.metrics.ending_equity - D(prior["end_usdc"])) < D("1e-20")
        assert abs(run.metrics.max_drawdown_pct - D(prior["dd_pct"])) < D("1e-20")
        scenarios[costs.name] = run
        proof["results"][label + "_" + costs.name] = {
            "ending_usdc": str(run.metrics.ending_equity),
            "dd_pct": str(run.metrics.max_drawdown_pct),
            "trades": run.metrics.completed_trades,
            "matched_prior_experiment": True,
        }
        print(label, costs.name, proof["results"][label + "_" + costs.name], flush=True)
    config_hash = hashlib.sha256(
        json.dumps(strategy.config_payload(), sort_keys=True).encode()
    ).hexdigest()
    report = write_report_bundle(
        scenarios=scenarios,
        output_root=data / "verified-reports" / label,
        config_sha256=config_hash,
        code_commit="RESEARCH_WORKTREE_BASE_15b78e8_UNCOMMITTED_PYTHON_IDENTIFIED_BY_SHA256",
        report_start_utc=s,
        report_end_utc=end,
        strategy=strategy,
        history_data=continuity_manifest_data(history),
        trading_settings={
            "auto_budget_enabled": True,
            "autonomous_performance_enabled": True,
            "slot_count": 2,
            "capital_exposure_fraction": "0.35",
            "profit_reinvestment_fraction": "1",
        },
        capital_source={
            "kind": "DATED_SIMULATION_REFERENCE_NO_PRIVATE_API_ACCESS",
            "starting_cash_usdc": str(seed),
        },
    )
    proof[label + "_report"] = str(report)
(data / "candidate-proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
